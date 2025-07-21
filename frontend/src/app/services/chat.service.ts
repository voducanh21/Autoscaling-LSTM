import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { Observable, of, TimeoutError } from 'rxjs';
import { catchError, tap, timeout, map, retry } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private apiUrl = 'http://localhost:8888/api/chat';  

  constructor(private http: HttpClient) {
    console.log('ChatService initialized with URL:', this.apiUrl);
  }

  sendMessage(message: string): Observable<any> {
    console.log('=== ChatService.sendMessage ===');
    console.log('Message:', message);
    
    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    });
    
    // Backend ChatController có thể nhận input dạng { message: string }
    const payload = { message };
    
    return this.http.post<any>(this.apiUrl, payload, { headers })
    .pipe(
      // Thử lại request 1 lần nếu lỗi
      retry(1),
      
      // Giảm timeout xuống 30s thay vì 60s
      timeout(30000),
      
      // Log chi tiết response để debug
      tap(response => {
        console.log('=== Response received ===');
        console.log('Response type:', typeof response);
        console.log('Response:', response);
        
        // Kiểm tra thêm các trường từ backend
        if (response) {
          console.log('Has success:', response.success !== undefined);
          console.log('Has reply:', response.reply !== undefined);
          console.log('Has assistantResponse:', response.assistantResponse !== undefined);
          console.log('Has message:', response.message !== undefined);
        }
      }),
      
      map(response => {
        // Xử lý response null/undefined
        if (!response) {
          console.warn('Response is null or undefined');
          return { 
            success: false,
            reply: 'Không nhận được dữ liệu từ server' 
          };
        }
        
        // Xử lý string response (hiếm gặp)
        if (typeof response === 'string') {
          try {
            return JSON.parse(response);
          } catch (e) {
            return { success: true, reply: response };
          }
        }
        
        // Xử lý object response từ backend
        // Backend luôn trả về nhiều trường: reply, message, assistantResponse
        let reply = null;
        
        // Ưu tiên trường 'reply' từ backend
        if (response.reply) {
          reply = response.reply;
        } 
        // Backup: dùng 'assistantResponse' từ backend
        else if (response.assistantResponse) {
          reply = response.assistantResponse;
        } 
        // Backup: dùng 'message' từ backend
        else if (response.message) {
          reply = response.message;
        }
        // Fallback nếu không có field nào
        else {
          console.warn('Response is missing expected fields:', response);
          reply = 'Server trả về dữ liệu không đúng định dạng';
        }
        
        return {
          success: response.success !== false, // Mặc định true nếu không được chỉ định
          reply: reply
        };
      }),
      
      catchError((error: HttpErrorResponse | TimeoutError) => {
        console.error('=== Chat Error ===');
        console.error('Error type:', error.constructor.name);
        
        // TimeoutError xử lý riêng (từ RxJS)
        if (error instanceof TimeoutError) {
          return of({
            success: false,
            reply: 'Server phản hồi quá chậm. Vui lòng thử lại sau.'
          });
        }
        
        // HttpErrorResponse xử lý riêng
        if (error instanceof HttpErrorResponse) {
          console.error('Status:', error.status);
          console.error('StatusText:', error.statusText);
          console.error('Message:', error.message);
          console.error('URL:', error.url);
          console.error('Error:', error.error);
          
          // CORS hoặc network issue (status = 0)
          if (error.status === 0) {
            return of({
              success: false,
              reply: 'Không thể kết nối đến server. Vui lòng kiểm tra mạng và thử lại.'
            });
          }
          
          // Server errors (5xx)
          if (error.status >= 500) {
            return of({
              success: false,
              reply: `Lỗi server: ${error.status}. Vui lòng thử lại sau.`
            });
          }
          
          // Client errors (4xx)
          if (error.status >= 400 && error.status < 500) {
            return of({
              success: false,
              reply: `Lỗi yêu cầu: ${error.status}. Vui lòng thử lại.`
            });
          }
        }
        
        // Fallback cho các lỗi khác
        return of({
          success: false,
          reply: 'Có lỗi xảy ra. Vui lòng thử lại sau.'
        });
      })
    );
  }

  getMessages(): Observable<any[]> {
    return this.http.get<any[]>(this.apiUrl).pipe(
      retry(1),
      timeout(10000),
      catchError(error => {
        console.error('Error fetching messages:', error);
        return of([]);
      })
    );
  }

  clearMessages(): Observable<any> {
    return this.http.delete<any>(this.apiUrl).pipe(
      retry(1),
      timeout(10000),
      catchError(error => {
        console.error('Error clearing messages:', error);
        return of({ success: false });
      })
    );
  }
}