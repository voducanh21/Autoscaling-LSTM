package com.shop.chat.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import java.time.LocalDateTime;

@Document(collection = "chats")
public class ChatMessage {
    
    @Id
    private String id;
    private String userMessage;
    private String assistantResponse;
    private LocalDateTime timestamp;
    
    public ChatMessage() {
        this.timestamp = LocalDateTime.now();
    }
    
    public ChatMessage(String userMessage, String assistantResponse) {
        this.userMessage = userMessage;
        this.assistantResponse = assistantResponse;
        this.timestamp = LocalDateTime.now();
    }
    
    // Getters and Setters
    public String getId() {
        return id;
    }
    
    public void setId(String id) {
        this.id = id;
    }
    
    public String getUserMessage() {
        return userMessage;
    }
    
    public void setUserMessage(String userMessage) {
        this.userMessage = userMessage;
    }
    
    public String getAssistantResponse() {
        return assistantResponse;
    }
    
    public void setAssistantResponse(String assistantResponse) {
        this.assistantResponse = assistantResponse;
    }
    
    public LocalDateTime getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }
}