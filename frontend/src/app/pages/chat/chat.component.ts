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

  

  constructor(private chatService: ChatService) {}

  ngOnInit() {
    this.loadChatHistory();
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  // Add trackByMessageId method
  trackByMessageId(index: number, message: ChatMessage): string {
    return message.id || index.toString();
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
      text: '⏳ Thinking...',
      timestamp: new Date(),
      id: 'loading'
    };
    this.messages.push(loadingMsg);
    
    const sendSubscription = this.chatService.sendMessage(userMessage).subscribe({
      next: (response) => {
        this.messages = this.messages.filter(msg => msg.id !== 'loading');
        
        let replyText = '';
        if (response.error) {
          replyText = response.message || 'Sorry, an error occurred. Please try again.';
        } else {
          replyText = response.reply || response.message || 'I do not understand your question. Could you please rephrase it?';
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
          text: 'Sorry, I am having connection issues. Please try again later.',
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
    if (this.isLoading) return 'Sending...';
    if (this.isConnected) return 'Connected';
    return 'Disconnected';
  }

  getConnectionStatusClass(): string {
    if (this.isLoading) return 'text-yellow-600';
    if (this.isConnected) return 'text-green-600';
    return 'text-red-600';
  }
}