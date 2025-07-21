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

    const userId = localStorage.getItem('userId');
    if (!userId) {
      console.error('UserId not found in localStorage. Please login.');
      return of({
        success: false,
        reply: 'You must be logged in to use the chat.'
      });
    }
    
    const headers = new HttpHeaders({
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    });
    
    // Backend ChatController can accept input in the form { message: string }
    const payload = { userId, message };
    
    return this.http.post<any>(this.apiUrl, payload, { headers })
    .pipe(
      // Retry the request once on error
      retry(1),
      
      // Reduce timeout to 30s instead of 60s
      timeout(30000),
      
      // Log the detailed response for debugging
      tap(response => {
        console.log('=== Response received ===');
        console.log('Response type:', typeof response);
        console.log('Response:', response);
        
        // Check for additional fields from the backend
        if (response) {
          console.log('Has success:', response.success !== undefined);
          console.log('Has reply:', response.reply !== undefined);
          console.log('Has assistantResponse:', response.assistantResponse !== undefined);
          console.log('Has message:', response.message !== undefined);
        }
      }),
      
      catchError((error: HttpErrorResponse | TimeoutError) => {
        console.error('=== Chat Error ===');
        console.error('Error type:', error.constructor.name);
        
        // Handle TimeoutError separately (from RxJS)
        if (error instanceof TimeoutError) {
          return of({
            success: false,
            reply: 'Server took too long to respond. Please try again later.'
          });
        }
        
        // Handle HttpErrorResponse separately
        if (error instanceof HttpErrorResponse) {
          console.error('Status:', error.status);
          console.error('StatusText:', error.statusText);
          console.error('Message:', error.message);
          console.error('URL:', error.url);
          console.error('Error:', error.error);
          
          // CORS or network issue (status = 0)
          if (error.status === 0) {
            return of({
              success: false,
              reply: 'Cannot connect to the server. Please check your network and try again.'
            });
          }
          
          // Server errors (5xx)
          if (error.status >= 500) {
            return of({
              success: false,
              reply: `Server error: ${error.status}. Please try again later.`
            });
          }
          
          // Client errors (4xx)
          if (error.status >= 400 && error.status < 500) {
            return of({
              success: false,
              reply: `Request error: ${error.status}. Please try again.`
            });
          }
        }
        
        // Fallback for other errors
        return of({
          success: false,
          reply: 'An unexpected error occurred. Please try again later.'
        });
      })
    );
  }

  getMessages(): Observable<any[]> {
    const userId = localStorage.getItem('userId');
    if (!userId) {
      return of([]);
    }
    return this.http.get<any[]>(`${this.apiUrl}/${userId}`).pipe(
      retry(1),
      timeout(10000),
      catchError(error => {
        console.error('Error fetching messages:', error);
        return of([]);
      })
    );
  }

  clearMessages(): Observable<any> {
    const userId = localStorage.getItem('userId');
    if (!userId) {
      return of({ success: false });
    }
    return this.http.delete<any>(`${this.apiUrl}/${userId}`).pipe(
      retry(1),
      timeout(10000),
      catchError(error => {
        console.error('Error clearing messages:', error);
        return of({ success: false });
      })
    );
  }
}