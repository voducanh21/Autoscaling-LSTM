import { Component, OnInit, OnDestroy, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import { Subscription } from 'rxjs';

interface ChatMessage {
  from: 'user' | 'bot';
  text: string;
  timestamp?: Date;
  id?: string;
}

@Component({
  selector: 'app-chat',
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.css']
})
export class ChatComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('chatMessages') private chatMessagesContainer!: ElementRef;
  
  messages: ChatMessage[] = [];
  userInput = '';
  isLoading = false;
  isConnected = false;
  private subscriptions: Subscription[] = [];

  // Thêm property quickSuggestions
  quickSuggestions = [
    'Tôi muốn tìm điện thoại',
    'Sản phẩm nào đang khuyến mãi?',
    'Cách thức thanh toán',
    'Chính sách đổi trả',
    'Thời gian giao hàng'
  ];

  constructor(private chatService: ChatService) {}

  ngOnInit() {
    this.initializeChat();
    this.loadChatHistory();
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  // Thêm method trackByMessageId
  trackByMessageId(index: number, message: ChatMessage): string {
    return message.id || index.toString();
  }

  private initializeChat() {
    this.messages.push({
      from: 'bot',
      text: 'Xin chào! Tôi là trợ lý tự động của AnD Shop. Tôi có thể giúp bạn tư vấn sản phẩm và trả lời các câu hỏi. Bạn cần hỗ trợ gì?',
      timestamp: new Date(),
      id: this.generateId()
    });
  }

  private loadChatHistory() {
    const historySubscription = this.chatService.getMessages().subscribe({
      next: (history) => {
        if (history && history.length > 0) {
          if (this.messages.length <= 1) {
            const historyMessages = history.map(msg => ({
              from: msg.from || 'bot',
              text: msg.text || msg.message || '',
              timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
              id: msg.id || this.generateId()
            }));
            this.messages = [...historyMessages, ...this.messages];
          }
        }
        this.isConnected = true;
      },
      error: (error) => {
        console.log('Could not load chat history:', error);
        this.isConnected = false;
      }
    });
    
    this.subscriptions.push(historySubscription);
  }

  send() {
    if (!this.userInput.trim() || this.isLoading) return;
    
    const userMessage = this.userInput.trim();
    const userMsg: ChatMessage = {
      from: 'user',
      text: userMessage,
      timestamp: new Date(),
      id: this.generateId()
    };
    
    this.messages.push(userMsg);
    this.userInput = '';
    this.isLoading = true;
    
    const loadingMsg: ChatMessage = {
      from: 'bot',
      text: '⏳ Đang suy nghĩ...',
      timestamp: new Date(),
      id: 'loading'
    };
    this.messages.push(loadingMsg);
    
    const sendSubscription = this.chatService.sendMessage(userMessage).subscribe({
      next: (response) => {
        this.messages = this.messages.filter(msg => msg.id !== 'loading');
        
        let replyText = '';
        if (response.error) {
          replyText = response.message || 'Xin lỗi, có lỗi xảy ra. Vui lòng thử lại.';
        } else {
          replyText = response.reply || response.message || 'Tôi không hiểu câu hỏi của bạn. Bạn có thể diễn đạt lại được không?';
        }
        
        const botMsg: ChatMessage = {
          from: 'bot',
          text: replyText,
          timestamp: new Date(),
          id: this.generateId()
        };
        
        this.messages.push(botMsg);
        this.isLoading = false;
        this.isConnected = true;
      },
      error: (error) => {
        this.messages = this.messages.filter(msg => msg.id !== 'loading');
        
        const errorMsg: ChatMessage = {
          from: 'bot',
          text: 'Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại sau.',
          timestamp: new Date(),
          id: this.generateId()
        };
        
        this.messages.push(errorMsg);
        this.isLoading = false;
        this.isConnected = false;
        console.error('Chat error:', error);
      }
    });
    
    this.subscriptions.push(sendSubscription);
  }

  clearChat() {
    const clearSubscription = this.chatService.clearMessages().subscribe({
      next: () => {
        this.messages = [];
        this.initializeChat();
      },
      error: (error) => {
        console.error('Error clearing chat:', error);
      }
    });
    
    this.subscriptions.push(clearSubscription);
  }

  private scrollToBottom(): void {
    try {
      this.chatMessagesContainer.nativeElement.scrollTop = 
        this.chatMessagesContainer.nativeElement.scrollHeight;
    } catch(err) {}
  }

  private generateId(): string {
    return Math.random().toString(36).substr(2, 9);
  }

  onKeyPress(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  getConnectionStatus(): string {
    if (this.isLoading) return 'Đang gửi...';
    if (this.isConnected) return 'Đã kết nối';
    return 'Mất kết nối';
  }

  getConnectionStatusClass(): string {
    if (this.isLoading) return 'text-yellow-600';
    if (this.isConnected) return 'text-green-600';
    return 'text-red-600';
  }
}