//+------------------------------------------------------------------+
//|                                              TelegramBridge.mq5  |
//|                                  Copyright 2026, Auto-Trade Bot  |
//|                                             https://github.com/  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Auto-Trade Bot"
#property link      "https://github.com/"
#property version   "1.00"

// Import thư viện chuẩn
#include <Trade\Trade.mqh>
#include "HttpClient.mqh"
#include "JsonParser.mqh"

// Inputs cấu hình từ người dùng
input string   InpApiUrl         = "http://127.0.0.1:8000";   // REST API URL
input string   InpApiKey         = "testkey";                  // X-API-Key
input int      InpPollMs         = 500;                        // Thời gian quét (ms)
input int      InpMaxSlippage    = 10;                         // Slippage tối đa (pips)
input int      InpMagicNumber    = 202606;                     // Magic Number

// Biến toàn cục
HttpClient     *g_http;
CTrade         g_trade;
string         g_executed_uuids[];
int            g_uuids_count = 0;
int            g_tick_counter = 0;
const string   FILE_DEDUP = "executed_trades.csv";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("Initializing TelegramBridge EA...");
   
   // 1. Khởi tạo Http client
   g_http = new HttpClient(InpApiUrl, InpApiKey);
   
   // 2. Cấu hình CTrade
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpMaxSlippage);
   
   // 3. Đọc danh sách UUID đã khớp từ file để tránh đặt trùng lệnh (deduplication)
   LoadExecutedUuids();
   
   // 4. Thiết lập Timer
   EventSetMillisecondTimer(InpPollMs);
   
   Print("TelegramBridge EA Initialized successfully.");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("Deinitializing TelegramBridge EA...");
   EventKillTimer();
   if(g_http != NULL)
   {
      delete g_http;
   }
}

//+------------------------------------------------------------------+
//| Expert timer function                                            |
//+------------------------------------------------------------------+
void OnTimer()
{
   g_tick_counter++;
   
   // 1. Poll PENDING trades (Mỗi tick ~500ms)
   PollPendingTrades();
   
   // 2. Poll CLOSE requests (Mỗi tick ~500ms)
   PollCloseRequests();
   
   // 3. Sync positions (Mỗi 2 ticks ~ 1 giây)
   if(g_tick_counter % 2 == 0)
   {
      SyncPositions();
   }
   
   // 4. Sync Account & Heartbeat (Mỗi 10 ticks ~ 5 giây)
   if(g_tick_counter % 10 == 0)
   {
      SyncAccountAndHeartbeat();
   }
}

//+------------------------------------------------------------------+
//| Quét và thực hiện các lệnh PENDING                                |
//+------------------------------------------------------------------+
void PollPendingTrades()
{
   string response = "";
   int code = g_http.Get("/api/trades?status=PENDING", response);
   if(code != 200) return;
   
   TradeData trades[];
   int count = JsonParser.ParseTradeArray(response, trades);
   
   for(int i = 0; i < count; i++)
   {
      string uuid = trades[i].uuid;
      int trade_id = trades[i].id;
      
      // Kiểm tra trùng lặp
      if(IsUuidExecuted(uuid))
      {
         Print("Phát hiện lệnh trùng lặp UUID: ", uuid, ". Hủy và đánh dấu FAILED.");
         UpdateTradeStatus(trade_id, "FAILED", 0, 0, 0, "DUPLICATE_UUID");
         continue;
      }
      
      // Thực thi đặt lệnh
      int ticket = 0;
      double execution_price = 0.0;
      string error_msg = "";
      
      bool ok = ExecuteTrade(trades[i], ticket, execution_price, error_msg);
      
      if(ok)
      {
         Print("Giao dịch thành công. Ticket #", ticket, ", Giá: ", execution_price);
         // Ghi nhận UUID vào cache và file
         SaveExecutedUuid(uuid);
         // Cập nhật trạng thái FILLED về API
         UpdateTradeStatus(trade_id, "FILLED", ticket, execution_price, 0, "");
      }
      else
      {
         Print("Giao dịch thất bại. Lỗi: ", error_msg);
         // Cập nhật trạng thái FAILED về API
         UpdateTradeStatus(trade_id, "FAILED", 0, 0, GetLastError(), error_msg);
      }
   }
}

//+------------------------------------------------------------------+
//| Quét và thực hiện các yêu cầu đóng lệnh (CLOSE_REQUESTED)        |
//+------------------------------------------------------------------+
void PollCloseRequests()
{
   string response = "";
   int code = g_http.Get("/api/trades?status=FILLED&close_requested=1", response);
   if(code != 200) return;
   
   TradeData trades[];
   int count = JsonParser.ParseTradeArray(response, trades);
   
   for(int i = 0; i < count; i++)
   {
      int ticket = trades[i].ticket;
      int trade_id = trades[i].id;
      
      if(ticket <= 0) continue;
      
      Print("Nhận yêu cầu đóng lệnh Ticket #", ticket);
      bool ok = g_trade.PositionClose(ticket, InpMaxSlippage);
      if(ok)
      {
         Print("Đã gửi yêu cầu đóng lệnh Ticket #", ticket, " thành công.");
         // Note: Trạng thái CLOSED sẽ được cập nhật tự động trong luồng SyncPositions()
      }
      else
      {
         Print("Gửi yêu cầu đóng lệnh Ticket #", ticket, " thất bại. Lỗi: ", g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| Đồng bộ các vị thế đang chạy về API                              |
//+------------------------------------------------------------------+
void SyncPositions()
{
   int positions_count = PositionsTotal();
   string json = "{\"positions\":[";
   
   int added = 0;
   for(int i = 0; i < positions_count; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      if(PositionSelectByTicket(ticket))
      {
         string symbol = PositionGetString(POSITION_SYMBOL);
         double volume = PositionGetDouble(POSITION_VOLUME);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double sl = PositionGetDouble(POSITION_SL);
         double tp = PositionGetDouble(POSITION_TP);
         double pnl = PositionGetDouble(POSITION_PROFIT);
         double swap = PositionGetDouble(POSITION_SWAP);
         double commission = PositionGetDouble(POSITION_COMMISSION);
         datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
         
         long type = PositionGetInteger(POSITION_TYPE);
         string type_str = (type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
         
         // Định dạng ISO 8601 thời gian
         MqlDateTime mql_time;
         TimeToStruct(open_time, mql_time);
         string time_str = StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ", 
            mql_time.year, mql_time.mon, mql_time.day, mql_time.hour, mql_time.min, mql_time.sec);
         
         if(added > 0) json += ",";
         
         json += StringFormat(
            "{\"ticket\":%I64u,\"symbol\":\"%s\",\"trade_type\":\"%s\",\"lot_size\":%.2f,"
            "\"open_price\":%.5f,\"current_price\":%.5f,\"stop_loss\":%.5f,\"take_profit\":%.5f,"
            "\"pnl\":%.2f,\"swap\":%.2f,\"commission\":%.2f,\"open_time\":\"%s\"}",
            ticket, symbol, type_str, volume, open_price, current_price, sl, tp, pnl, swap, commission, time_str
         );
         added++;
      }
   }
   
   json += "]}";
   
   string response = "";
   g_http.Put("/api/positions", json, response);
}

//+------------------------------------------------------------------+
//| Đồng bộ thông tin tài khoản và Heartbeat                          |
//+------------------------------------------------------------------+
void SyncAccountAndHeartbeat()
{
   // 1. Đồng bộ Account Info
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin = AccountInfoDouble(ACCOUNT_FREE_MARGIN);
   double profit = AccountInfoDouble(ACCOUNT_PROFIT);
   string server = AccountInfoString(ACCOUNT_SERVER);
   long acc_num = AccountInfoInteger(ACCOUNT_LOGIN);
   string acc_name = AccountInfoString(ACCOUNT_NAME);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   
   string json = StringFormat(
      "{\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,\"profit\":%.2f,"
      "\"server\":\"%s\",\"account_number\":%I64d,\"account_name\":\"%s\",\"currency\":\"%s\",\"leverage\":%I64d}",
      balance, equity, margin, free_margin, profit, server, acc_num, acc_name, currency, leverage
   );
   
   string response = "";
   g_http.Put("/api/account", json, response);
}

//+------------------------------------------------------------------+
//| Đặt lệnh giao dịch trên MT5                                      |
//+------------------------------------------------------------------+
bool ExecuteTrade(TradeData &trade, int &out_ticket, double &out_price, string &out_error_msg)
{
   out_ticket = 0;
   out_price = 0.0;
   out_error_msg = "";
   
   string symbol = trade.symbol;
   double volume = trade.lot_size;
   string type = trade.trade_type;
   
   // 1. Kiểm tra symbol hợp lệ
   if(!SymbolSelect(symbol, true))
   {
      out_error_msg = "Symbol không tồn tại trên sàn hoặc không thể kích hoạt: " + symbol;
      return false;
   }
   
   // 2. Xử lý SL / TP
   double sl = trade.stop_loss;
   double tp = trade.take_profit;
   
   // 3. Thực hiện đặt lệnh Market deal hoặc Pending
   if(type == "BUY" || type == "SELL")
   {
      double price = (type == "BUY") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
      
      bool res = false;
      if(type == "BUY")
      {
         res = g_trade.Buy(volume, symbol, price, sl, tp, "TG:" + trade.uuid);
      }
      else
      {
         res = g_trade.Sell(volume, symbol, price, sl, tp, "TG:" + trade.uuid);
      }
      
      if(res && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
      {
         out_ticket = (int)g_trade.ResultOrder();
         out_price = g_trade.ResultPrice();
         return true;
      }
      else
      {
         out_error_msg = g_trade.ResultRetcodeDescription() + " (Code: " + IntegerToString(g_trade.ResultRetcode()) + ")";
         return false;
      }
   }
   else
   {
      // Các lệnh Pending (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP)
      ENUM_ORDER_TYPE order_type;
      if(type == "BUY_LIMIT") order_type = ORDER_TYPE_BUY_LIMIT;
      else if(type == "SELL_LIMIT") order_type = ORDER_TYPE_SELL_LIMIT;
      else if(type == "BUY_STOP") order_type = ORDER_TYPE_BUY_STOP;
      else if(type == "SELL_STOP") order_type = ORDER_TYPE_SELL_STOP;
      else
      {
         out_error_msg = "Không hỗ trợ loại lệnh: " + type;
         return false;
      }
      
      double price = trade.price;
      if(price <= 0)
      {
         out_error_msg = "Lệnh Pending yêu cầu giá khớp hợp lệ.";
         return false;
      }
      
      bool res = g_trade.OrderOpen(symbol, order_type, volume, price, price, sl, tp, ORDER_TIME_GTC, 0, "TG:" + trade.uuid);
      if(res && (g_trade.ResultRetcode() == TRADE_RETCODE_DONE || g_trade.ResultRetcode() == TRADE_RETCODE_PLACED))
      {
         out_ticket = (int)g_trade.ResultOrder();
         out_price = price;
         return true;
      }
      else
      {
         out_error_msg = g_trade.ResultRetcodeDescription() + " (Code: " + IntegerToString(g_trade.ResultRetcode()) + ")";
         return false;
      }
   }
}

//+------------------------------------------------------------------+
//| Cập nhật trạng thái lệnh về REST API                            |
//+------------------------------------------------------------------+
void UpdateTradeStatus(int trade_id, string status, int ticket, double open_price, int err_code, string err_msg)
{
   string json = "{\"status\":\"" + status + "\"";
   
   if(ticket > 0)
   {
      json += ",\"ticket\":" + IntegerToString(ticket);
   }
   if(open_price > 0.0)
   {
      json += StringFormat(",\"open_price\":%.5f", open_price);
   }
   if(err_code > 0)
   {
      json += ",\"error_code\":" + IntegerToString(err_code);
   }
   if(err_msg != "")
   {
      json += ",\"error_msg\":\"" + err_msg + "\"";
   }
   json += "}";
   
   string response = "";
   g_http.Put("/api/trades/" + IntegerToString(trade_id), json, response);
}

//+------------------------------------------------------------------+
//| Kiểm tra xem UUID đã được giao dịch chưa (Deduplication)         |
//+------------------------------------------------------------------+
bool IsUuidExecuted(const string uuid)
{
   for(int i = 0; i < g_uuids_count; i++)
   {
      if(g_executed_uuids[i] == uuid) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Đọc danh sách UUID đã khớp từ file                               |
//+------------------------------------------------------------------+
void LoadExecutedUuids()
{
   ArrayFree(g_executed_uuids);
   g_uuids_count = 0;
   
   if(!FileIsExist(FILE_DEDUP)) return;
   
   int handle = FileOpen(FILE_DEDUP, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;
   
   while(!FileIsEnding(handle))
   {
      string uuid = FileReadString(handle);
      if(uuid == "") continue;
      
      g_uuids_count++;
      ArrayResize(g_executed_uuids, g_uuids_count);
      g_executed_uuids[g_uuids_count - 1] = uuid;
   }
   
   FileClose(handle);
   Print("Loaded ", g_uuids_count, " executed UUIDs from deduplication file.");
}

//+------------------------------------------------------------------+
//| Lưu UUID đã khớp vào file và cache                               |
//+------------------------------------------------------------------+
void SaveExecutedUuid(const string uuid)
{
   // Thêm vào cache bộ nhớ
   g_uuids_count++;
   ArrayResize(g_executed_uuids, g_uuids_count);
   g_executed_uuids[g_uuids_count - 1] = uuid;
   
   // Ghi tiếp vào file
   int handle = FileOpen(FILE_DEDUP, FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle != INVALID_HANDLE)
   {
      FileSeek(handle, 0, SEEK_END);
      FileWrite(handle, uuid);
      FileClose(handle);
   }
}
