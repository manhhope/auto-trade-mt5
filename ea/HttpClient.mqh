//+------------------------------------------------------------------+
//|                                                   HttpClient.mqh |
//|                                  Copyright 2026, Auto-Trade Bot  |
//|                                             https://github.com/  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Auto-Trade Bot"
#property link      "https://github.com/"
#property version   "1.00"

//+------------------------------------------------------------------+
//| Class HttpClient                                                 |
//+------------------------------------------------------------------+
class HttpClient
{
private:
   string   m_base_url;
   string   m_api_key;
   int      m_timeout;

   string   BuildHeaders()
   {
      return "Content-Type: application/json\r\n" +
             "X-Account-Token: " + m_api_key + "\r\n";
   }

public:
   HttpClient(const string base_url, const string api_key, int timeout_ms = 5000)
   {
      m_base_url = base_url;
      // Đảm bảo không có dấu gạch chéo ở cuối URL base
      if(StringSubstr(m_base_url, StringLen(m_base_url) - 1, 1) == "/")
      {
         m_base_url = StringSubstr(m_base_url, 0, StringLen(m_base_url) - 1);
      }
      m_api_key = api_key;
      m_timeout = timeout_ms;
   }

   ~HttpClient() {}

   // Gửi GET Request
   int Get(const string endpoint, string &out_response)
   {
      string url = m_base_url + endpoint;
      string headers = BuildHeaders();
      uchar post_data[]; // Rỗng đối với GET
      uchar result_data[];
      string result_headers;

      ResetLastError();
      int res = WebRequest("GET", url, headers, m_timeout, post_data, result_data, result_headers);
      
      if(res == -1)
      {
         int err = GetLastError();
         Print("GET WebRequest error: ", err);
         out_response = "{\"error_code\": " + IntegerToString(err) + ", \"error_msg\": \"WebRequest failed\"}";
         return -1;
      }

      out_response = CharArrayToString(result_data, 0, WHOLE_ARRAY, CP_UTF8);
      return res;
   }

   // Gửi POST Request
   int Post(const string endpoint, const string json_body, string &out_response)
   {
      string url = m_base_url + endpoint;
      string headers = BuildHeaders();
      uchar post_data[];
      StringToCharArray(json_body, post_data, 0, WHOLE_ARRAY, CP_UTF8);
      
      // MQL5: ArraySize của post_data cần bớt đi ký tự null cuối cùng
      int data_len = ArraySize(post_data);
      if(data_len > 0 && post_data[data_len - 1] == 0)
      {
         ArrayResize(post_data, data_len - 1);
      }

      uchar result_data[];
      string result_headers;

      ResetLastError();
      int res = WebRequest("POST", url, headers, m_timeout, post_data, result_data, result_headers);
      
      if(res == -1)
      {
         int err = GetLastError();
         Print("POST WebRequest error: ", err);
         out_response = "{\"error_code\": " + IntegerToString(err) + ", \"error_msg\": \"WebRequest failed\"}";
         return -1;
      }

      out_response = CharArrayToString(result_data, 0, WHOLE_ARRAY, CP_UTF8);
      return res;
   }

   // Gửi PUT Request
   int Put(const string endpoint, const string json_body, string &out_response)
   {
      string url = m_base_url + endpoint;
      string headers = BuildHeaders();
      uchar post_data[];
      StringToCharArray(json_body, post_data, 0, WHOLE_ARRAY, CP_UTF8);
      
      int data_len = ArraySize(post_data);
      if(data_len > 0 && post_data[data_len - 1] == 0)
      {
         ArrayResize(post_data, data_len - 1);
      }

      uchar result_data[];
      string result_headers;

      ResetLastError();
      int res = WebRequest("PUT", url, headers, m_timeout, post_data, result_data, result_headers);
      
      if(res == -1)
      {
         int err = GetLastError();
         Print("PUT WebRequest error: ", err);
         out_response = "{\"error_code\": " + IntegerToString(err) + ", \"error_msg\": \"WebRequest failed\"}";
         return -1;
      }

      out_response = CharArrayToString(result_data, 0, WHOLE_ARRAY, CP_UTF8);
      return res;
   }
};
