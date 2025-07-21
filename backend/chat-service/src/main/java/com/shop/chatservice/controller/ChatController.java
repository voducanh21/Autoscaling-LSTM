package com.shop.chatservice.controller;

import com.shop.chatservice.model.ChatMessage;
import com.shop.chatservice.service.ChatService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
public class ChatController {

    @Autowired
    private ChatService chatService;

    @PostMapping
    public ResponseEntity<Map<String, Object>> chat(@RequestBody ChatRequest payload) {
        Map<String, Object> response = new HashMap<>();
        System.out.println("Received payload: " + payload);
        
        try {
            String userId = payload.getUserId();
            String message = payload.getMessage();
            
            if (userId == null || userId.isEmpty() || message == null || message.isEmpty()) {
                response.put("success", false);
                response.put("message", "userId and message are required");
                return ResponseEntity.badRequest().body(response);
            }
            
            System.out.println("Received message from userId: " + userId + " - message: " + message);
            
            // Call the Gemini API to get a response and save the chat
            String aiResponse = chatService.chatWithGemini(userId, message);
            System.out.println("AI Response: " + aiResponse);
            
            // Return a response with multiple formats for frontend processing
            response.put("success", true);
            response.put("reply", aiResponse);
            response.put("assistantResponse", aiResponse);
            response.put("message", aiResponse);
            
            System.out.println("Sending response: " + response);
            
            return ResponseEntity.ok()
                .header("Content-Type", "application/json")
                .body(response);
                
        } catch (Exception e) {
            System.err.println("Error in chat endpoint: " + e.getMessage());
            e.printStackTrace();
            
            response.put("success", false);
            response.put("error", true);
            response.put("message", "Error processing message: " + e.getMessage());
            response.put("reply", "Sorry, an error occurred while processing your message.");
            
            return ResponseEntity.status(500)
                .header("Content-Type", "application/json")
                .body(response);
        }
    }
    
    @GetMapping("/{userId}")
    public ResponseEntity<List<Map<String, String>>> getMessages(@PathVariable String userId) {
        try {
            List<ChatMessage> chatHistory = chatService.getChatHistory(userId);
            List<Map<String, String>> formattedHistory = new ArrayList<>();
            
            // Reverse the order to display from oldest to newest
            for (int i = chatHistory.size() - 1; i >= 0; i--) {
                ChatMessage message = chatHistory.get(i);
                
                // Add user message
                Map<String, String> userMessage = new HashMap<>();
                userMessage.put("from", "user");
                userMessage.put("text", message.getUserMessage());
                formattedHistory.add(userMessage);
                
                // Add bot response
                Map<String, String> botMessage = new HashMap<>();
                botMessage.put("from", "bot");
                botMessage.put("text", message.getAssistantResponse());
                formattedHistory.add(botMessage);
            }
            
            System.out.println("Returning " + formattedHistory.size() + " messages for userId: " + userId);
            return ResponseEntity.ok()
                .header("Content-Type", "application/json")
                .body(formattedHistory);
                
        } catch (Exception e) {
            System.err.println("Error getting messages: " + e.getMessage());
            return ResponseEntity.ok(new ArrayList<>());
        }
    }
    
    @DeleteMapping("/{userId}")
    public ResponseEntity<Map<String, Object>> clearMessages(@PathVariable String userId) {
        Map<String, Object> response = new HashMap<>();
        try {
            chatService.clearChatHistory(userId);
            response.put("success", true);
            response.put("message", "Chat history cleared successfully.");
            return ResponseEntity.ok().body(response);
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "Error clearing chat history: " + e.getMessage());
            return ResponseEntity.status(500).body(response);
        }
    }
}