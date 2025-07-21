package com.shop.chatservice.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import java.time.LocalDateTime;

@Document(collection = "chats")
public class ChatMessage {
    
    @Id
    private String id;
    private String userId;
    private String userMessage;
    private String assistantResponse;
    private LocalDateTime timestamp;
    
    public ChatMessage() {
        this.timestamp = LocalDateTime.now();
    }
    
    public ChatMessage(String userId, String userMessage, String assistantResponse) {
        this.userId = userId;
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

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
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