package com.shop.chatservice.controller;

public class ChatRequest {
    private String userId;
    private String message;

    public String getUserId() {
        return userId;
    }

    public void setUserId(String userId) {
        this.userId = userId;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    @Override
    public String toString() {
        return "ChatRequest{" +
                "userId='" + userId + '\'' +
                ", message='" + message + '\'' +
                '}';
    }
}
