//+------------------------------------------------------------------+
//|                                                   JsonParser.mqh |
//|                                  Copyright 2026, Auto-Trade Bot  |
//|                                             https://github.com/  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Auto-Trade Bot"
#property link      "https://github.com/"
#property version   "1.00"

// Struct chứa thông tin lệnh nhận được từ API
struct TradeData
{
   int      id;
   string   uuid;
   string   symbol;
   string   trade_type;
   double   lot_size;
   double   price;
   double   stop_loss;
   double   take_profit;
   ulong    ticket;
   bool     close_requested;
};

//+------------------------------------------------------------------+
//| Class JsonParser                                                 |
//+------------------------------------------------------------------+
class JsonParser
{
private:
   // Trích xuất giá trị thô theo key (không bao gồm dấu ngoặc kép)
   string ExtractValue(const string json, const string key)
   {
      string search_key = "\"" + key + "\"";
      int start_pos = StringFind(json, search_key);
      if(start_pos == -1) return "";
      
      start_pos += StringLen(search_key);
      
      // Tìm vị trí bắt đầu giá trị (bỏ qua khoảng trắng và dấu hai chấm)
      int len = StringLen(json);
      int val_start = -1;
      for(int i = start_pos; i < len; i++)
      {
         ushort char_code = StringGetCharacter(json, i);
         if(char_code != ' ' && char_code != ':' && char_code != '\t')
         {
            val_start = i;
            break;
         }
      }
      
      if(val_start == -1) return "";
      
      // Nếu là String (bắt đầu bằng dấu ngoặc kép)
      if(StringGetCharacter(json, val_start) == '"')
      {
         val_start++; // Bỏ qua dấu ngoặc kép bắt đầu
         int val_end = StringFind(json, "\"", val_start);
         if(val_end == -1) return "";
         return StringSubstr(json, val_start, val_end - val_start);
      }
      
      // Nếu là số, boolean hoặc null (kết thúc bằng dấu phẩy, dấu đóng ngoặc nhọn hoặc xuống dòng)
      int val_end = -1;
      for(int i = val_start; i < len; i++)
      {
         ushort char_code = StringGetCharacter(json, i);
         if(char_code == ',' || char_code == '}' || char_code == ']' || char_code == '\r' || char_code == '\n' || char_code == ' ')
         {
            val_end = i;
            break;
         }
      }
      
      if(val_end == -1) val_end = len;
      string raw_val = StringSubstr(json, val_start, val_end - val_start);
      if(raw_val == "null") return "";
      return raw_val;
   }

public:
   JsonParser() {}
   ~JsonParser() {}

   // Lấy chuỗi
   string GetString(const string json, const string key)
   {
      return ExtractValue(json, key);
   }

   // Lấy số thực
   double GetDouble(const string json, const string key)
   {
      string val = ExtractValue(json, key);
      if(val == "") return 0.0;
      return StringToDouble(val);
   }

   // Lấy số nguyên
   int GetInteger(const string json, const string key)
   {
      string val = ExtractValue(json, key);
      if(val == "") return 0;
      return (int)StringToInteger(val);
   }
   
   // Lấy số ulong
   ulong GetUlong(const string json, const string key)
   {
      string val = ExtractValue(json, key);
      if(val == "") return 0;
      return (ulong)StringToInteger(val);
   }
   
   // Lấy boolean
   bool GetBool(const string json, const string key)
   {
      string val = ExtractValue(json, key);
      return (val == "true" || val == "1");
   }

   // Parse một mảng JSON các object trade: [ {...}, {...} ]
   int ParseTradeArray(const string json_array, TradeData &out_trades[])
   {
      ArrayFree(out_trades);
      
      int start_pos = StringFind(json_array, "[");
      int end_pos = StringFind(json_array, "]", start_pos);
      if(start_pos == -1 || end_pos == -1) return 0;
      
      string content = StringSubstr(json_array, start_pos + 1, end_pos - start_pos - 1);
      int count = 0;
      
      int current_pos = 0;
      int content_len = StringLen(content);
      
      while(current_pos < content_len)
      {
         int obj_start = StringFind(content, "{", current_pos);
         if(obj_start == -1) break;
         
         int obj_end = StringFind(content, "}", obj_start);
         if(obj_end == -1) break;
         
         string obj_str = StringSubstr(content, obj_start, obj_end - obj_start + 1);
         
         // Resize và đưa dữ liệu vào struct
         ArrayResize(out_trades, count + 1);
         out_trades[count].id = GetInteger(obj_str, "id");
         out_trades[count].uuid = GetString(obj_str, "uuid");
         out_trades[count].symbol = GetString(obj_str, "symbol");
         out_trades[count].trade_type = GetString(obj_str, "trade_type");
         out_trades[count].lot_size = GetDouble(obj_str, "lot_size");
         out_trades[count].price = GetDouble(obj_str, "price");
         out_trades[count].stop_loss = GetDouble(obj_str, "stop_loss");
         out_trades[count].take_profit = GetDouble(obj_str, "take_profit");
         out_trades[count].ticket = GetUlong(obj_str, "ticket");
         out_trades[count].close_requested = GetBool(obj_str, "close_requested");
         
         count++;
         current_pos = obj_end + 1;
      }
      
      return count;
   }

   // Parse một mảng số nguyên đơn giản từ JSON: "key":[1,2,3]
   int ParseIntArray(const string json, const string key, int &out_array[])
   {
      ArrayFree(out_array);
      string search_key = "\"" + key + "\"";
      int key_pos = StringFind(json, search_key);
      if(key_pos == -1) return 0;
      
      int start_bracket = StringFind(json, "[", key_pos);
      int end_bracket = StringFind(json, "]", start_bracket);
      if(start_bracket == -1 || end_bracket == -1) return 0;
      
      string array_str = StringSubstr(json, start_bracket + 1, end_bracket - start_bracket - 1);
      if(array_str == "") return 0;
      
      string parts[];
      int count = StringSplit(array_str, ',', parts);
      
      int added = 0;
      for(int i = 0; i < count; i++)
      {
         string clean_part = parts[i];
         StringTrimLeft(clean_part);
         StringTrimRight(clean_part);
         if(clean_part == "") continue;
         
         long val = StringToInteger(clean_part);
         if(val > 0)
         {
            added++;
            ArrayResize(out_array, added);
            out_array[added - 1] = (int)val;
         }
      }
      return added;
   }

   // Parse một mảng số ulong đơn giản từ JSON: "key":[1,2,3]
   int ParseUlongArray(const string json, const string key, ulong &out_array[])
   {
      ArrayFree(out_array);
      string search_key = "\"" + key + "\"";
      int key_pos = StringFind(json, search_key);
      if(key_pos == -1) return 0;
      
      int start_bracket = StringFind(json, "[", key_pos);
      int end_bracket = StringFind(json, "]", start_bracket);
      if(start_bracket == -1 || end_bracket == -1) return 0;
      
      string array_str = StringSubstr(json, start_bracket + 1, end_bracket - start_bracket - 1);
      if(array_str == "") return 0;
      
      string parts[];
      int count = StringSplit(array_str, ',', parts);
      
      int added = 0;
      for(int i = 0; i < count; i++)
      {
         string clean_part = parts[i];
         StringTrimLeft(clean_part);
         StringTrimRight(clean_part);
         if(clean_part == "") continue;
         
         long val = StringToInteger(clean_part);
         if(val > 0)
         {
            added++;
            ArrayResize(out_array, added);
            out_array[added - 1] = (ulong)val;
         }
      }
      return added;
   }
};
