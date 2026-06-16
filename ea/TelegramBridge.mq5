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
input string   InpApiKey         = "";                         // Account Connection Token
input int      InpPollMs         = 500;                        // Thời gian quét (ms)
input int      InpMaxSlippage    = 10;                         // Slippage tối đa (pips)
input int      InpMagicNumber    = 202606;                     // Magic Number

// Biến toàn cục
HttpClient     *g_http;
CTrade         g_trade;
JsonParser     g_json;
string         g_executed_uuids[];
int            g_uuids_count = 0;
int            g_tick_counter = 0;
const string   FILE_DEDUP = "executed_trades.csv";
const string   FILE_PARTIAL = "partial_closed.csv";

// Trailing Stop & Partial Close Global Configuration (đọc từ API)
bool   g_trail_enabled = false;
int    g_trail_be_pips = 15;
int    g_trail_be_offset = 2;
int    g_trail_step_pips = 10;
int    g_trail_step_distance = 8;
bool   g_trail_manual_enabled = false;
bool   g_partial_enabled = false;
int    g_partial_pips = 30;
double g_partial_ratio = 0.5;

// Mảng theo dõi các tickets đã chốt một phần (cũ)
ulong  g_partial_closed_tickets[];
int    g_partial_count = 0;

// Cấu hình chốt lời từng phần nhiều bước (mới)
string g_partial_ratios_str = "33/33/33";
string g_partial_pips_stages_str = "50/100/";
double g_partial_ratios[];
int    g_partial_pips_stages[];
int    g_num_stages = 0;

struct PartialStageState
{
   ulong ticket;
   int   stage;
};
PartialStageState g_partial_stages[];
int g_partial_stages_count = 0;

//+------------------------------------------------------------------+
//| Helper: Định dạng thời gian sang chuỗi ISO 8601                   |
//+------------------------------------------------------------------+
string GetIsoTimeString(datetime time)
{
   MqlDateTime dt;
   TimeToStruct(time, dt);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d", dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
}

//+------------------------------------------------------------------+
//| Phân tách chuỗi cấu hình các bước chốt lời                        |
//+------------------------------------------------------------------+
void ParseStages()
{
   string ratio_parts[];
   int ratio_count = StringSplit(g_partial_ratios_str, '/', ratio_parts);
   
   string pip_parts[];
   int pip_count = StringSplit(g_partial_pips_stages_str, '/', pip_parts);
   
   g_num_stages = ratio_count;
   ArrayResize(g_partial_ratios, g_num_stages);
   ArrayResize(g_partial_pips_stages, g_num_stages);
   
   for(int i = 0; i < g_num_stages; i++)
   {
      g_partial_ratios[i] = StringToDouble(ratio_parts[i]) / 100.0;
      
      if(i < pip_count && pip_parts[i] != "")
      {
         g_partial_pips_stages[i] = (int)StringToInteger(pip_parts[i]);
      }
      else
      {
         g_partial_pips_stages[i] = 0;
      }
   }
}

//+------------------------------------------------------------------+
//| Tải danh sách tickets đã chốt từng phần theo stage từ file        |
//+------------------------------------------------------------------+
void LoadCompletedStages()
{
   ArrayFree(g_partial_stages);
   g_partial_stages_count = 0;
   
   if(!FileIsExist("partial_stages.csv")) return;
   
   int handle = FileOpen("partial_stages.csv", FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;
   
   while(!FileIsEnding(handle))
   {
      string ticket_str = FileReadString(handle);
      string stage_str = FileReadString(handle);
      if(ticket_str == "" || stage_str == "") continue;
      
      ulong ticket = StringToInteger(ticket_str);
      int stage = (int)StringToInteger(stage_str);
      if(ticket <= 0 || stage <= 0) continue;
      
      bool found = false;
      for(int i = 0; i < g_partial_stages_count; i++)
      {
         if(g_partial_stages[i].ticket == ticket)
         {
            if(stage > g_partial_stages[i].stage)
            {
               g_partial_stages[i].stage = stage;
            }
            found = true;
            break;
         }
      }
      
      if(!found)
      {
         g_partial_stages_count++;
         ArrayResize(g_partial_stages, g_partial_stages_count);
         g_partial_stages[g_partial_stages_count - 1].ticket = ticket;
         g_partial_stages[g_partial_stages_count - 1].stage = stage;
      }
   }
   
   FileClose(handle);
   Print("Loaded ", g_partial_stages_count, " ticket stage states from partial_stages.csv.");
}

//+------------------------------------------------------------------+
//| Lấy stage chốt lời cao nhất đã hoàn thành của ticket              |
//+------------------------------------------------------------------+
int GetCompletedStage(ulong ticket)
{
   for(int i = 0; i < g_partial_stages_count; i++)
   {
      if(g_partial_stages[i].ticket == ticket)
      {
         return g_partial_stages[i].stage;
      }
   }
   return 0;
}

//+------------------------------------------------------------------+
//| Lưu stage chốt lời mới hoàn thành của ticket vào file và cache     |
//+------------------------------------------------------------------+
void SaveCompletedStage(ulong ticket, int stage)
{
   bool found = false;
   for(int i = 0; i < g_partial_stages_count; i++)
   {
      if(g_partial_stages[i].ticket == ticket)
      {
         g_partial_stages[i].stage = stage;
         found = true;
         break;
      }
   }
   
   if(!found)
   {
      g_partial_stages_count++;
      ArrayResize(g_partial_stages, g_partial_stages_count);
      g_partial_stages[g_partial_stages_count - 1].ticket = ticket;
      g_partial_stages[g_partial_stages_count - 1].stage = stage;
   }
   
   int handle = FileOpen("partial_stages.csv", FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(handle != INVALID_HANDLE)
   {
      for(int i = 0; i < g_partial_stages_count; i++)
      {
         FileWrite(handle, IntegerToString(g_partial_stages[i].ticket), IntegerToString(g_partial_stages[i].stage));
      }
      FileClose(handle);
   }
}

//+------------------------------------------------------------------+
//| Lấy khối lượng vào lệnh ban đầu (Initial Volume) của vị thế      |
//+------------------------------------------------------------------+
double GetPositionInitialVolume(ulong position_id)
{
   if(!HistorySelectByPosition(position_id)) return 0.0;
   int deals_total = HistoryDealsTotal();
   for(int i = 0; i < deals_total; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket > 0)
      {
         long entry = HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_IN)
         {
            return HistoryDealGetDouble(deal_ticket, DEAL_VOLUME);
         }
      }
   }
   return 0.0;
}

//+------------------------------------------------------------------+
//| Báo cáo lịch sử thao tác của EA lên REST API                      |
//+------------------------------------------------------------------+
void ReportActionLog(ulong ticket, string symbol, string action_type, string details, double pnl, double current_price, double lot_size, string trade_type)
{
   string req_body = "{\"ticket\":" + IntegerToString(ticket) +
                     ",\"symbol\":\"" + symbol + "\"" +
                     ",\"action_type\":\"" + action_type + "\"" +
                     ",\"details\":\"" + details + "\"" +
                     ",\"pnl\":" + DoubleToString(pnl, 2) +
                     ",\"current_price\":" + DoubleToString(current_price, 5) +
                     ",\"lot_size\":" + DoubleToString(lot_size, 2) +
                     ",\"trade_type\":\"" + trade_type + "\"}";
                     
   string response = "";
   int code = g_http.Post("/api/action-logs", req_body, response);
   if(code == 200)
   {
      Print("Reported action log to API successfully: ", action_type, " for ticket #", ticket);
   }
   else
   {
      Print("FAILED to report action log. Code: ", code, ", Response: ", response);
   }
}

//+------------------------------------------------------------------+
//| Đồng bộ lịch sử các lệnh đã đóng lên REST API                    |
//+------------------------------------------------------------------+
void SyncClosedTrades()
{
   datetime now = TimeCurrent();
   datetime from_time = now - 3600; // quét lịch sử trong 1 giờ qua
   
   if(!HistorySelect(from_time, now)) return;
   int total_deals = HistoryDealsTotal();
   
   ulong closed_tickets[];
   int closed_count = 0;
   
   for(int i = 0; i < total_deals; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket <= 0) continue;
      
      long entry = HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      {
         ulong position_id = (ulong)HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID);
         if(position_id <= 0) continue;
         
         bool processed = false;
         for(int j = 0; j < closed_count; j++)
         {
            if(closed_tickets[j] == position_id) { processed = true; break; }
         }
         if(processed) continue;
         
         closed_count++;
         ArrayResize(closed_tickets, closed_count);
         closed_tickets[closed_count - 1] = position_id;
      }
   }
   
   if(closed_count == 0) return;
   
   string json_trades = "";
   int batch_count = 0;
   
   for(int i = 0; i < closed_count; i++)
   {
      ulong position_id = closed_tickets[i];
      
      if(!HistorySelectByPosition(position_id)) continue;
      
      int p_deals = HistoryDealsTotal();
      double open_price = 0.0;
      double close_price = 0.0;
      double lot_size = 0.0;
      double pnl = 0.0;
      double commission = 0.0;
      double swap = 0.0;
      datetime opened_at = 0;
      datetime closed_at = 0;
      string symbol = "";
      string trade_type = "";
      string close_reason = "MANUAL";
      
      for(int j = 0; j < p_deals; j++)
      {
         ulong d_ticket = HistoryDealGetTicket(j);
         if(d_ticket <= 0) continue;
         
         long entry = HistoryDealGetInteger(d_ticket, DEAL_ENTRY);
         long d_type = HistoryDealGetInteger(d_ticket, DEAL_TYPE);
         
         if(entry == DEAL_ENTRY_IN)
         {
            open_price = HistoryDealGetDouble(d_ticket, DEAL_PRICE);
            opened_at = (datetime)HistoryDealGetInteger(d_ticket, DEAL_TIME);
            symbol = HistoryDealGetString(d_ticket, DEAL_SYMBOL);
            trade_type = (d_type == DEAL_TYPE_BUY) ? "BUY" : "SELL";
            lot_size = HistoryDealGetDouble(d_ticket, DEAL_VOLUME);
         }
         else if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
         {
            close_price = HistoryDealGetDouble(d_ticket, DEAL_PRICE);
            closed_at = (datetime)HistoryDealGetInteger(d_ticket, DEAL_TIME);
            pnl += HistoryDealGetDouble(d_ticket, DEAL_PROFIT);
            commission += HistoryDealGetDouble(d_ticket, DEAL_COMMISSION);
            swap += HistoryDealGetDouble(d_ticket, DEAL_SWAP);
            
            string comment = HistoryDealGetString(d_ticket, DEAL_COMMENT);
            if(StringFind(comment, "sl") >= 0 || StringFind(comment, "SL") >= 0) close_reason = "SL_HIT";
            else if(StringFind(comment, "tp") >= 0 || StringFind(comment, "TP") >= 0) close_reason = "TP_HIT";
            else if(StringFind(comment, "trailing") >= 0 || StringFind(comment, "ts") >= 0) close_reason = "TRAILING_STOP";
         }
      }
      
      if(opened_at > 0 && closed_at > 0)
      {
         string opened_at_str = GetIsoTimeString(opened_at);
         string closed_at_str = GetIsoTimeString(closed_at);
         
         string trade_json = "{"
            "\"ticket\":" + IntegerToString(position_id) + ","
            "\"symbol\":\"" + symbol + "\","
            "\"trade_type\":\"" + trade_type + "\","
            "\"lot_size\":" + DoubleToString(lot_size, 2) + ","
            "\"open_price\":" + DoubleToString(open_price, 5) + ","
            "\"close_price\":" + DoubleToString(close_price, 5) + ","
            "\"pnl\":" + DoubleToString(pnl, 2) + ","
            "\"commission\":" + DoubleToString(commission, 2) + ","
            "\"swap\":" + DoubleToString(swap, 2) + ","
            "\"opened_at\":\"" + opened_at_str + "\","
            "\"closed_at\":\"" + closed_at_str + "\","
            "\"close_reason\":\"" + close_reason + "\""
            "}";
            
         if(json_trades != "") json_trades += ",";
         json_trades += trade_json;
         batch_count++;
      }
   }
   
   if(batch_count > 0)
   {
      string req_body = "{\"trades\":[" + json_trades + "]}";
      string response = "";
      int code = g_http.Post("/api/trades/sync-closed", req_body, response);
      if(code != 200)
      {
         Print("FAILED to sync closed trades. Code: ", code, ", Response: ", response);
      }
   }
}

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
   LoadPartialClosedTickets();
   LoadCompletedStages();
   
   // 4. Kiểm tra kết nối tới REST API
   string test_resp = "";
   int test_code = g_http.Get("/api/health", test_resp);
   if(test_code == 200)
   {
      Print("Connected to REST API successfully. API Response: ", test_resp);
   }
   else
   {
      Print("WARNING: FAILED to connect to REST API! HTTP code: ", test_code, ", Response: ", test_resp);
      Print("Vui long kiem tra lai InpApiUrl, InpApiKey, va chac chan rang ban da cho phep WebRequest den URL nay trong MT5 Options.");
   }
   
   // 5. Thiết lập Timer
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
//| Lấy kích thước Pip của symbol                                     |
//+------------------------------------------------------------------+
double GetPipSize(string symbol)
{
   // Nếu là Vàng (XAUUSDm hoặc GOLD) thì 1 pip mặc định là 0.1$ (10 cents)
   if(StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "GOLD") >= 0 || StringFind(symbol, "gold") >= 0)
   {
      return 0.1;
   }
   
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   
   if(digits == 3 || digits == 5 || digits == 2)
   {
      return point * 10.0;
   }
   return point;
}

//+------------------------------------------------------------------+
//| Làm chuẩn khối lượng Volume giao dịch                            |
//+------------------------------------------------------------------+
double NormalizeVolume(string symbol, double volume)
{
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   
   if(volume < min_lot) return min_lot;
   if(volume > max_lot) return max_lot;
   
   double normalized = MathRound(volume / step_lot) * step_lot;
   return NormalizeDouble(normalized, 2);
}

//+------------------------------------------------------------------+
//| Kiểm tra xem ticket đã partial close chưa                        |
//+------------------------------------------------------------------+
bool IsTicketPartialClosed(ulong ticket)
{
   for(int i = 0; i < g_partial_count; i++)
   {
      if(g_partial_closed_tickets[i] == ticket) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Tải danh sách tickets đã partial close từ file                   |
//+------------------------------------------------------------------+
void LoadPartialClosedTickets()
{
   ArrayFree(g_partial_closed_tickets);
   g_partial_count = 0;
   
   if(!FileIsExist(FILE_PARTIAL)) return;
   
   int handle = FileOpen(FILE_PARTIAL, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;
   
   while(!FileIsEnding(handle))
   {
      string ticket_str = FileReadString(handle);
      if(ticket_str == "") continue;
      
      ulong ticket = StringToInteger(ticket_str);
      if(ticket <= 0) continue;
      
      g_partial_count++;
      ArrayResize(g_partial_closed_tickets, g_partial_count);
      g_partial_closed_tickets[g_partial_count - 1] = ticket;
   }
   
   FileClose(handle);
   Print("Loaded ", g_partial_count, " partial closed tickets from file.");
}

//+------------------------------------------------------------------+
//| Lưu ticket đã partial close vào file và cache                    |
//+------------------------------------------------------------------+
void SavePartialClosedTicket(ulong ticket)
{
   if(IsTicketPartialClosed(ticket)) return;
   
   g_partial_count++;
   ArrayResize(g_partial_closed_tickets, g_partial_count);
   g_partial_closed_tickets[g_partial_count - 1] = ticket;
   
   int handle = FileOpen(FILE_PARTIAL, FILE_WRITE|FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(handle != INVALID_HANDLE)
   {
      FileSeek(handle, 0, SEEK_END);
      FileWrite(handle, IntegerToString(ticket));
      FileClose(handle);
   }
}

//+------------------------------------------------------------------+
//| Lấy cấu hình Trailing Stop mới nhất từ REST API                   |
//+------------------------------------------------------------------+
void PollTrailingConfig()
{
   string response = "";
   int code = g_http.Get("/api/config/trailing", response);
   if(code != 200)
   {
      Print("FAILED to fetch trailing config. HTTP code: ", code);
      return;
   }
   
   g_trail_enabled        = g_json.GetBool(response, "enabled");
   g_trail_be_pips        = g_json.GetInteger(response, "be_pips");
   g_trail_be_offset      = g_json.GetInteger(response, "be_offset");
   g_trail_step_pips      = g_json.GetInteger(response, "step_pips");
   g_trail_step_distance  = g_json.GetInteger(response, "step_distance");
   g_trail_manual_enabled = g_json.GetBool(response, "manual_enabled");
   g_partial_enabled      = g_json.GetBool(response, "partial_enabled");
   g_partial_pips         = g_json.GetInteger(response, "partial_pips");
   g_partial_ratio        = g_json.GetDouble(response, "partial_ratio");
   
   // Đọc cấu hình chốt lời nhiều bước mới
   string partial_ratios_api = g_json.GetString(response, "partial_ratios");
   if(partial_ratios_api != "") g_partial_ratios_str = partial_ratios_api;

   string partial_pips_stages_api = g_json.GetString(response, "partial_pips_stages");
   if(partial_pips_stages_api != "") g_partial_pips_stages_str = partial_pips_stages_api;
   
   ParseStages();
}

//+------------------------------------------------------------------+
//| Quản lý Trailing Stop và Chốt lời một phần                        |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
   int positions_count = PositionsTotal();
   for(int i = 0; i < positions_count; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      if(PositionSelectByTicket(ticket))
      {
         long magic = PositionGetInteger(POSITION_MAGIC);
         if(magic != InpMagicNumber)
         {
            if(!g_trail_manual_enabled || magic != 0) continue;
         }
         
         string symbol = PositionGetString(POSITION_SYMBOL);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
         double sl = PositionGetDouble(POSITION_SL);
         double tp = PositionGetDouble(POSITION_TP);
         double volume = PositionGetDouble(POSITION_VOLUME);
         long type = PositionGetInteger(POSITION_TYPE);
         
         double pip_size = GetPipSize(symbol);
         if(pip_size <= 0) continue;
         
         int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
         
         // 1. Tính lợi nhuận theo pips
         double profit_pips = 0.0;
         if(type == POSITION_TYPE_BUY)
         {
            profit_pips = (current_price - open_price) / pip_size;
         }
         else if(type == POSITION_TYPE_SELL)
         {
            profit_pips = (open_price - current_price) / pip_size;
         }
         else
         {
            continue;
         }
         
         // 2. Xử lý Trailing Stop (Giai đoạn 1 & 2)
         if(g_trail_enabled && profit_pips >= g_trail_be_pips)
         {
            int steps = 0;
            if(g_trail_step_pips > 0)
            {
               steps = (int)((profit_pips - g_trail_be_pips) / g_trail_step_pips);
            }
            if(steps < 0) steps = 0;
            
            double new_sl = 0.0;
            if(type == POSITION_TYPE_BUY)
            {
               new_sl = open_price + (g_trail_be_offset + steps * g_trail_step_distance) * pip_size;
               new_sl = NormalizeDouble(new_sl, digits);
               
               if(sl < new_sl - 0.1 * pip_size)
               {
                  Print("Trailing SL cho lệnh BUY #", ticket, ": Dời từ ", sl, " -> ", new_sl);
                  if(g_trade.PositionModify(ticket, new_sl, tp))
                  {
                     double current_pnl = PositionGetDouble(POSITION_PROFIT);
                     string details_str = DoubleToString(sl, digits) + " -> " + DoubleToString(new_sl, digits);
                     ReportActionLog(ticket, symbol, "TRAILING_SL", details_str, current_pnl, current_price, volume, "BUY");
                  }
                  else
                  {
                     Print("LỖI dời SL lệnh BUY #", ticket, ": ", g_trade.ResultRetcodeDescription());
                  }
               }
            }
            else if(type == POSITION_TYPE_SELL)
            {
               new_sl = open_price - (g_trail_be_offset + steps * g_trail_step_distance) * pip_size;
               new_sl = NormalizeDouble(new_sl, digits);
               
               if(sl == 0.0 || sl > new_sl + 0.1 * pip_size)
               {
                  Print("Trailing SL cho lệnh SELL #", ticket, ": Dời từ ", sl, " -> ", new_sl);
                  if(g_trade.PositionModify(ticket, new_sl, tp))
                  {
                     double current_pnl = PositionGetDouble(POSITION_PROFIT);
                     string details_str = DoubleToString(sl, digits) + " -> " + DoubleToString(new_sl, digits);
                     ReportActionLog(ticket, symbol, "TRAILING_SL", details_str, current_pnl, current_price, volume, "SELL");
                  }
                  else
                  {
                     Print("LỖI dời SL lệnh SELL #", ticket, ": ", g_trade.ResultRetcodeDescription());
                  }
               }
            }
         }
         
         // 3. Xử lý Chốt lời từng phần nhiều bước (Multi-stage Partial Close)
         if(g_partial_enabled && g_num_stages > 0)
         {
            double initial_volume = GetPositionInitialVolume(ticket);
            if(initial_volume > 0.01) // Bỏ qua nếu volume ban đầu <= 0.01 lot
            {
               int completed_stage = GetCompletedStage(ticket);
               int next_stage = completed_stage + 1;
               
               if(next_stage <= g_num_stages)
               {
                  int target_pips = g_partial_pips_stages[next_stage - 1];
                  
                  // Chỉ chốt nếu có target_pips được thiết lập (> 0) và lợi nhuận đạt yêu cầu
                  if(target_pips > 0 && profit_pips >= target_pips)
                  {
                     double close_volume = initial_volume * g_partial_ratios[next_stage - 1];
                     close_volume = NormalizeVolume(symbol, close_volume);
                     
                     // Làm tròn ở bước cuối cùng hoặc khi khối lượng chốt lớn hơn khối lượng hiện tại
                     if(next_stage == g_num_stages || close_volume >= volume)
                     {
                        close_volume = volume;
                     }
                     
                     if(close_volume > 0 && close_volume <= volume)
                     {
                        Print("Chốt lời từng phần bước ", next_stage, "/", g_num_stages, " cho lệnh #", ticket, ": Khớp ", close_volume, " lot.");
                        
                        bool close_ok = false;
                        if(close_volume == volume)
                        {
                           close_ok = g_trade.PositionClose(ticket, InpMaxSlippage);
                        }
                        else
                        {
                           close_ok = g_trade.PositionClosePartial(ticket, close_volume, InpMaxSlippage);
                        }
                        
                        if(close_ok)
                        {
                           Print("Đã chốt lời từng phần bước ", next_stage, " thành công.");
                           SaveCompletedStage(ticket, next_stage);
                           
                           double current_pnl = PositionGetDouble(POSITION_PROFIT);
                           double est_realized_pnl = (current_pnl / volume) * close_volume;
                           
                           string details_str = IntegerToString(next_stage) + "/" + IntegerToString(g_num_stages);
                           string t_type = type == POSITION_TYPE_BUY ? "BUY" : "SELL";
                           ReportActionLog(ticket, symbol, "PARTIAL_CLOSE", details_str, est_realized_pnl, current_price, close_volume, t_type);
                        }
                        else
                        {
                           Print("LỖI chốt lời từng phần bước ", next_stage, ": ", g_trade.ResultRetcodeDescription());
                        }
                     }
                  }
               }
            }
         }
      }
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
   
   // Trailing stop & Partial Close — Mỗi tick
   if(g_trail_enabled || g_partial_enabled)
   {
      ManageTrailingStop();
   }
   
   // 3. Sync positions (Mỗi 2 ticks ~ 1 giây)
   if(g_tick_counter % 2 == 0)
   {
      SyncPositions();
   }
   
   // 4. Sync Account, Heartbeat, Closed Trades & Poll Config (Mỗi 10 ticks ~ 5 giây)
   if(g_tick_counter % 10 == 0)
   {
      PollTrailingConfig();
      SyncAccountAndHeartbeat();
      SyncClosedTrades();
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
   int count = g_json.ParseTradeArray(response, trades);
   
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
      ulong ticket = 0;
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
   int count = g_json.ParseTradeArray(response, trades);
   
   for(int i = 0; i < count; i++)
   {
      ulong ticket = trades[i].ticket;
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
         double commission = 0.0; // POSITION_COMMISSION is deprecated in MT5
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
   int code = g_http.Put("/api/positions", json, response);
   if(code == 200 && response != "")
   {
      ulong tickets_to_close[];
      int count = g_json.ParseUlongArray(response, "close_tickets", tickets_to_close);
      for(int i = 0; i < count; i++)
      {
         ulong ticket = tickets_to_close[i];
         if(ticket > 0)
         {
            Print("Nhận yêu cầu đóng vị thế Ticket #", ticket);
            if(g_trade.PositionClose(ticket, InpMaxSlippage))
            {
               Print("Đã gửi yêu cầu đóng vị thế Ticket #", ticket, " thành công.");
            }
            else
            {
               Print("Gửi yêu cầu đóng vị thế Ticket #", ticket, " thất bại: ", g_trade.ResultRetcodeDescription());
            }
         }
      }
   }
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
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double profit = AccountInfoDouble(ACCOUNT_PROFIT);
   string server = AccountInfoString(ACCOUNT_SERVER);
   long acc_num = AccountInfoInteger(ACCOUNT_LOGIN);
   string acc_name = AccountInfoString(ACCOUNT_NAME);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   
   // Lấy thông tin giá vàng và biến động xu hướng
   double gold_price = 0.0;
   double gold_change_1h = 0.0;
   double gold_change_4h = 0.0;
   double gold_change_1d = 0.0;
   
   string gold_symbol = "";
   if(StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "GOLD") >= 0)
   {
      gold_symbol = _Symbol;
   }
   else if(SymbolInfoInteger("XAUUSDm", SYMBOL_SELECT) || SymbolSelect("XAUUSDm", true))
   {
      gold_symbol = "XAUUSDm";
   }
   else if(SymbolInfoInteger("XAUUSD", SYMBOL_SELECT) || SymbolSelect("XAUUSD", true))
   {
      gold_symbol = "XAUUSD";
   }
   
   if(gold_symbol != "")
   {
      gold_price = SymbolInfoDouble(gold_symbol, SYMBOL_BID);
      
      MqlRates rates_h1[];
      MqlRates rates_h4[];
      MqlRates rates_d1[];
      
      ArraySetAsSeries(rates_h1, true);
      ArraySetAsSeries(rates_h4, true);
      ArraySetAsSeries(rates_d1, true);
      
      if(CopyRates(gold_symbol, PERIOD_H1, 0, 1, rates_h1) > 0)
      {
         gold_change_1h = gold_price - rates_h1[0].open;
      }
      if(CopyRates(gold_symbol, PERIOD_H4, 0, 1, rates_h4) > 0)
      {
         gold_change_4h = gold_price - rates_h4[0].open;
      }
      if(CopyRates(gold_symbol, PERIOD_D1, 0, 1, rates_d1) > 0)
      {
         gold_change_1d = gold_price - rates_d1[0].open;
      }
   }
   
   string json = StringFormat(
      "{\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,\"profit\":%.2f,"
      "\"server\":\"%s\",\"account_number\":%I64d,\"account_name\":\"%s\",\"currency\":\"%s\",\"leverage\":%I64d"
      ",\"gold_price\":%.2f,\"gold_change_1h\":%.2f,\"gold_change_4h\":%.2f,\"gold_change_1d\":%.2f}",
      balance, equity, margin, free_margin, profit, server, acc_num, acc_name, currency, leverage,
      gold_price, gold_change_1h, gold_change_4h, gold_change_1d
   );
   
   string response = "";
   g_http.Put("/api/account", json, response);
}

//+------------------------------------------------------------------+
//| Tự động làm đầy giá trị 2 số cuối thành giá đầy đủ               |
//+------------------------------------------------------------------+
double ExpandPrice(double parsed_val, double current_price)
{
   if(parsed_val <= 0.0) return 0.0;
   if(parsed_val >= 1000.0) return parsed_val; // Đã là giá đầy đủ (ví dụ 4192.5)
   
   // Lấy phần trăm/nghìn của giá hiện tại (ví dụ: 4192.5 -> base = 4100.0)
   double base = MathFloor(current_price / 100.0) * 100.0;
   
   double opt1 = base + parsed_val;
   double opt2 = base - 100.0 + parsed_val;
   double opt3 = base + 100.0 + parsed_val;
   
   double diff1 = MathAbs(opt1 - current_price);
   double diff2 = MathAbs(opt2 - current_price);
   double diff3 = MathAbs(opt3 - current_price);
   
   double best_val = opt1;
   double min_diff = diff1;
   
   if(diff2 < min_diff) { min_diff = diff2; best_val = opt2; }
   if(diff3 < min_diff) { min_diff = diff3; best_val = opt3; }
   
   return best_val;
}

//+------------------------------------------------------------------+
//| Đặt lệnh giao dịch trên MT5                                      |
//+------------------------------------------------------------------+
bool ExecuteTrade(TradeData &trade, ulong &out_ticket, double &out_price, string &out_error_msg)
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
   
   // 2. Xử lý SL / TP và làm đầy giá 2 số cuối nếu có
   double current_price = SymbolInfoDouble(symbol, SYMBOL_BID);
   if(current_price <= 0) current_price = SymbolInfoDouble(symbol, SYMBOL_ASK);
   
   if(current_price > 0)
   {
      trade.price = ExpandPrice(trade.price, current_price);
      trade.stop_loss = ExpandPrice(trade.stop_loss, current_price);
      trade.take_profit = ExpandPrice(trade.take_profit, current_price);
   }
   
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
         out_ticket = (ulong)g_trade.ResultOrder();
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
         out_ticket = (ulong)g_trade.ResultOrder();
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
void UpdateTradeStatus(int trade_id, string status, ulong ticket, double open_price, int err_code, string err_msg)
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
