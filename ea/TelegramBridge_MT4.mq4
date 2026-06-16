//+------------------------------------------------------------------+
//|                                             TelegramBridge_MT4.mq4|
//|                                  Copyright 2026, Auto-Trade Bot  |
//|                                             https://github.com/  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Auto-Trade Bot"
#property link      "https://github.com/"
#property version   "1.00"
#property strict

// Import HttpClient and JsonParser (compatible with MQL4)
#include "HttpClient.mqh"
#include "JsonParser.mqh"

// Inputs cấu hình từ người dùng
input string   InpApiUrl         = "http://127.0.0.1:8000";   // REST API URL
input string   InpApiKey         = "";                         // Account Connection Token
input int      InpPollMs         = 500;                        // Thời gian quét (ms)
input int      InpMaxSlippage    = 10;                         // Slippage tối đa (pips)
input int      InpMagicNumber    = 202606;                     // Magic Number

// Biến toàn cục
HttpClient     *g_http;
JsonParser     g_json;
int            g_tick_counter = 0;
const string   FILE_DEDUP = "executed_trades_mt4.csv";

// Helper chuyển đổi Time sang định dạng ISO 8601
string TimeToISO(datetime time)
{
   MqlDateTime dt;
   TimeToStruct(time, dt);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d", dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
}

// Kiểm tra xem lệnh đã xử lý chưa (tránh trùng lặp)
bool IsTradeExecuted(const string uuid)
{
   if(FileIsExist(FILE_DEDUP, FILE_COMMON))
   {
      int handle = FileOpen(FILE_DEDUP, FILE_READ|FILE_CSV|FILE_COMMON, ',');
      if(handle != INVALID_HANDLE)
      {
         while(!FileIsEnding(handle))
         {
            string line_uuid = FileReadString(handle);
            if(line_uuid == uuid)
            {
               FileClose(handle);
               return true;
            }
         }
         FileClose(handle);
      }
   }
   return false;
}

// Đánh dấu lệnh đã xử lý
void MarkTradeExecuted(const string uuid)
{
   int handle = FileOpen(FILE_DEDUP, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON, ',');
   if(handle != INVALID_HANDLE)
   {
      FileSeek(handle, 0, SEEK_END);
      FileWrite(handle, uuid, TimeToString(TimeCurrent()));
      FileClose(handle);
   }
}

// Khởi tạo EA
int OnInit()
{
   if(InpApiKey == "")
   {
      Alert("LỖI: Chưa cấu hình Account Connection Token!");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_http = new HttpClient(InpApiUrl, InpApiKey);
   EventSetMillisecondTimer(InpPollMs);
   
   Print("=== Telegram MT4 Bridge EA Started ===");
   Print("API URL: ", InpApiUrl);
   Print("Magic Number: ", InpMagicNumber);
   
   return INIT_SUCCEEDED;
}

// Giải phóng tài nguyên
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(CheckPointer(g_http) == POINTER_DYNAMIC)
   {
      delete g_http;
   }
   Print("=== Telegram MT4 Bridge EA Stopped ===");
}

// Xử lý Timer (Vòng lặp polling chính)
void OnTimer()
{
   g_tick_counter++;
   
   // 1. Quét lệnh PENDING từ API (Mỗi chu kỳ InpPollMs)
   PollPendingTrades();
   
   // 2. Quét yêu cầu đóng vị thế (Mỗi chu kỳ InpPollMs)
   PollCloseRequests();
   
   // 3. Đồng bộ tài khoản, vị thế và lịch sử (Mỗi ~30 giây)
   if(g_tick_counter >= (30000 / InpPollMs))
   {
      g_tick_counter = 0;
      SyncAccountInfo();
      SyncActivePositions();
      SyncClosedTrades();
   }
}

// Lấy lệnh PENDING từ API và thực thi
void PollPendingTrades()
{
   string response = "";
   int code = g_http.Get("/api/trades?status=PENDING", response);
   if(code != 200 || response == "" || response == "[]") return;
   
   TradeData trades[];
   int count = g_json.ParseTradeArray(response, trades);
   for(int i = 0; i < count; i++)
   {
      int trade_id = trades[i].id;
      string uuid = trades[i].uuid;
      string symbol = trades[i].symbol;
      string trade_type = trades[i].trade_type;
      double lot_size = trades[i].lot_size;
      double sl = trades[i].stop_loss;
      double tp = trades[i].take_profit;
      
      if(IsTradeExecuted(uuid))
      {
         // Lệnh đã thực thi trước đó, cập nhật DB để tránh treo PENDING
         ConfirmTradeExecution(trade_id, "FILLED", 0, 0, 0, "Duplicate request");
         continue;
      }
      
      ExecuteTrade(trade_id, uuid, symbol, trade_type, lot_size, sl, tp);
   }
}

// Thực hiện giao dịch trên MT4
void ExecuteTrade(int trade_id, string uuid, string symbol, string trade_type, double lot_size, double sl, double tp)
{
   int type = -1;
   if(trade_type == "BUY") type = OP_BUY;
   else if(trade_type == "SELL") type = OP_SELL;
   
   if(type == -1)
   {
      ConfirmTradeExecution(trade_id, "FAILED", 0, 0, ERR_INVALID_TRADE_PARAMETERS, "Unsupported trade type: " + trade_type);
      return;
   }
   
   // Check market price
   double price = 0.0;
   if(type == OP_BUY) price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   else price = SymbolInfoDouble(symbol, SYMBOL_BID);
   
   if(price == 0.0)
   {
      ConfirmTradeExecution(trade_id, "FAILED", 0, 0, ERR_UNKNOWN_SYMBOL, "Invalid symbol price: " + symbol);
      return;
   }
   
   ResetLastError();
   color clr = (type == OP_BUY) ? clrGreen : clrRed;
   int ticket = OrderSend(symbol, type, lot_size, price, InpMaxSlippage, sl, tp, "AutoTrade: " + uuid, InpMagicNumber, 0, clr);
   
   if(ticket < 0)
   {
      int err = GetLastError();
      string err_msg = ErrorDescription(err);
      Print("OrderSend error: ", err, " (", err_msg, ")");
      ConfirmTradeExecution(trade_id, "FAILED", 0, 0, err, err_msg);
   }
   else
   {
      MarkTradeExecuted(uuid);
      if(OrderSelect(ticket, SELECT_BY_TICKET))
      {
         ConfirmTradeExecution(trade_id, "FILLED", ticket, OrderOpenPrice(), 0, "Success");
      }
   }
}

// Cập nhật kết quả khớp lệnh lên API
void ConfirmTradeExecution(int trade_id, string status, int ticket, double open_price, int error_code, string error_msg)
{
   string json = "{";
   json += "\"status\": \"" + status + "\",";
   if(ticket > 0)
   {
      json += "\"ticket\": " + IntegerToString(ticket) + ",";
      json += "\"open_price\": " + DoubleToString(open_price, _Digits) + ",";
   }
   if(error_code > 0)
   {
      json += "\"error_code\": " + IntegerToString(error_code) + ",";
      json += "\"error_msg\": \"" + error_msg + "\",";
   }
   // Remove trailing comma
   if(StringSubstr(json, StringLen(json)-1, 1) == ",")
   {
      json = StringSubstr(json, 0, StringLen(json)-1);
   }
   json += "}";
   
   string response = "";
   g_http.Put("/api/trades/" + IntegerToString(trade_id), json, response);
}

// Quét các lệnh có yêu cầu đóng từ API và thực thi đóng
void PollCloseRequests()
{
   string response = "";
   // Poll các lệnh FILLED mà Bot yêu cầu đóng (close_requested=1)
   int code = g_http.Get("/api/trades?status=FILLED&close_requested=1", response);
   if(code != 200 || response == "" || response == "[]") return;
   
   TradeData trades[];
   int count = g_json.ParseTradeArray(response, trades);
   for(int i = 0; i < count; i++)
   {
      int trade_id = trades[i].id;
      int ticket = (int)trades[i].ticket;
      
      CloseTicket(trade_id, ticket);
   }
}

// Đóng lệnh theo ticket trên MT4
void CloseTicket(int trade_id, int ticket)
{
   if(!OrderSelect(ticket, SELECT_BY_TICKET))
   {
      // Không tìm thấy ticket, có thể đã bị đóng bằng tay
      UpdateClosedTradeInDB(trade_id, 0.0, 0.0, 0.0, 0.0, "MANUAL");
      return;
   }
   
   if(OrderCloseTime() > 0)
   {
      // Lệnh đã đóng trước đó
      UpdateClosedTradeInDB(trade_id, OrderClosePrice(), OrderProfit(), OrderCommission(), OrderSwap(), "MANUAL");
      return;
   }
   
   double price = 0.0;
   if(OrderType() == OP_BUY) price = SymbolInfoDouble(OrderSymbol(), SYMBOL_BID);
   else price = SymbolInfoDouble(OrderSymbol(), SYMBOL_ASK);
   
   ResetLastError();
   bool success = OrderClose(ticket, OrderLots(), price, InpMaxSlippage, clrOrange);
   
   if(!success)
   {
      int err = GetLastError();
      Print("OrderClose error for ticket ", ticket, ": ", err);
   }
   else
   {
      if(OrderSelect(ticket, SELECT_BY_TICKET))
      {
         UpdateClosedTradeInDB(trade_id, OrderClosePrice(), OrderProfit(), OrderCommission(), OrderSwap(), "MANUAL");
      }
   }
}

// Cập nhật lệnh đã đóng lên DB
void UpdateClosedTradeInDB(int trade_id, double close_price, double pnl, double commission, double swap, string reason)
{
   string json = StringFormat(
      "{\"status\": \"CLOSED\", \"close_price\": %s, \"pnl\": %s, \"commission\": %s, \"swap\": %s, \"close_reason\": \"%s\"}",
      DoubleToString(close_price, 5),
      DoubleToString(pnl, 2),
      DoubleToString(commission, 2),
      DoubleToString(swap, 2),
      reason
   );
   string response = "";
   g_http.Put("/api/trades/" + IntegerToString(trade_id), json, response);
}

// Đồng bộ thông tin tài khoản lên API
void SyncAccountInfo()
{
   string json = StringFormat(
      "{\"balance\": %s, \"equity\": %s, \"margin\": %s, \"free_margin\": %s, \"profit\": %s, "
      "\"server\": \"%s\", \"account_number\": %s, \"account_name\": \"%s\", \"currency\": \"%s\", \"leverage\": %s}",
      DoubleToString(AccountBalance(), 2),
      DoubleToString(AccountEquity(), 2),
      DoubleToString(AccountMargin(), 2),
      DoubleToString(AccountFreeMargin(), 2),
      DoubleToString(AccountProfit(), 2),
      AccountServer(),
      IntegerToString(AccountNumber()),
      AccountName(),
      AccountCurrency(),
      IntegerToString(AccountLeverage())
   );
   
   string response = "";
   g_http.Put("/api/account", json, response);
}

// Đồng bộ các lệnh đang chạy lên API
void SyncActivePositions()
{
   string json = "{\"positions\": [";
   int total = OrdersTotal();
   bool first = true;
   
   for(int i = 0; i < total; i++)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         if(OrderType() != OP_BUY && OrderType() != OP_SELL) continue;
         
         double current_price = (OrderType() == OP_BUY) ? 
            SymbolInfoDouble(OrderSymbol(), SYMBOL_BID) : 
            SymbolInfoDouble(OrderSymbol(), SYMBOL_ASK);
            
         string type_str = (OrderType() == OP_BUY) ? "BUY" : "SELL";
         
         if(!first) json += ",";
         first = false;
         
         json += StringFormat(
            "{\"ticket\": %s, \"symbol\": \"%s\", \"trade_type\": \"%s\", \"lot_size\": %s, "
            "\"open_price\": %s, \"current_price\": %s, \"stop_loss\": %s, \"take_profit\": %s, "
            "\"pnl\": %s, \"swap\": %s, \"commission\": %s, \"open_time\": \"%s\"}",
            IntegerToString(OrderTicket()),
            OrderSymbol(),
            type_str,
            DoubleToString(OrderLots(), 2),
            DoubleToString(OrderOpenPrice(), 5),
            DoubleToString(current_price, 5),
            DoubleToString(OrderStopLoss(), 5),
            DoubleToString(OrderTakeProfit(), 5),
            DoubleToString(OrderProfit(), 2),
            DoubleToString(OrderSwap(), 2),
            DoubleToString(OrderCommission(), 2),
            TimeToISO(OrderOpenTime())
         );
      }
   }
   json += "]}";
   
   string response = "";
   g_http.Put("/api/positions", json, response);
}

// Đồng bộ các lệnh đã đóng thủ công/tự động trong vòng 24 giờ qua
void SyncClosedTrades()
{
   int history_total = OrdersHistoryTotal();
   datetime cutoff = TimeCurrent() - 86400; // Lấy lịch sử 24 giờ qua
   string trades_json = "";
   bool first = true;
   
   for(int i = history_total - 1; i >= 0; i--)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
      {
         if(OrderType() != OP_BUY && OrderType() != OP_SELL) continue;
         if(OrderCloseTime() < cutoff) break; // Lịch sử sắp xếp theo thời gian đóng, gặp lệnh cũ thì dừng
         
         string type_str = (OrderType() == OP_BUY) ? "BUY" : "SELL";
         string reason = "MANUAL";
         
         // Đánh giá sơ bộ lý do đóng lệnh
         double close_price = OrderClosePrice();
         double sl = OrderStopLoss();
         double tp = OrderTakeProfit();
         
         if(sl > 0 && MathAbs(close_price - sl) < 2 * Point) reason = "SL_HIT";
         else if(tp > 0 && MathAbs(close_price - tp) < 2 * Point) reason = "TP_HIT";
         
         if(!first) trades_json += ",";
         first = false;
         
         trades_json += StringFormat(
            "{\"ticket\": %s, \"symbol\": \"%s\", \"trade_type\": \"%s\", \"lot_size\": %s, "
            "\"open_price\": %s, \"close_price\": %s, \"pnl\": %s, \"commission\": %s, \"swap\": %s, "
            "\"opened_at\": \"%s\", \"closed_at\": \"%s\", \"close_reason\": \"%s\"}",
            IntegerToString(OrderTicket()),
            OrderSymbol(),
            type_str,
            DoubleToString(OrderLots(), 2),
            DoubleToString(OrderOpenPrice(), 5),
            DoubleToString(close_price, 5),
            DoubleToString(OrderProfit(), 2),
            DoubleToString(OrderCommission(), 2),
            DoubleToString(OrderSwap(), 2),
            TimeToISO(OrderOpenTime()),
            TimeToISO(OrderCloseTime()),
            reason
         );
      }
   }
   
   if(trades_json != "")
   {
      string req_body = "{\"trades\": [" + trades_json + "]}";
      string response = "";
      g_http.Post("/api/trades/sync-closed", req_body, response);
   }
}

// Hàm lấy tên lỗi từ mã lỗi
string ErrorDescription(int err_code)
{
   switch(err_code)
   {
      case ERR_NO_ERROR:                  return "No error";
      case ERR_INVALID_TRADE_PARAMETERS:  return "Invalid trade parameters";
      case ERR_UNKNOWN_SYMBOL:            return "Unknown symbol";
      case ERR_MARKET_CLOSED:             return "Market is closed";
      case ERR_TRADE_DISABLED:            return "Trading is disabled";
      case ERR_NOT_ENOUGH_MONEY:          return "Not enough money to open position";
      case ERR_PRICE_CHANGED:             return "Price changed";
      case ERR_OFF_QUOTES:                return "Off quotes";
      case ERR_REQUOTE:                   return "Requote";
      case ERR_ORDER_LOCKED:              return "Order is locked";
      case ERR_TOO_MANY_REQUESTS:         return "Too many requests";
      case ERR_TRADE_CONTEXT_BUSY:        return "Trade context is busy";
      default:                            return "Error code " + IntegerToString(err_code);
   }
}
