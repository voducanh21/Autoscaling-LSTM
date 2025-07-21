package com.shop.chat.controller;

import com.shop.chat.model.ChatMessage;
import com.shop.chat.repository.ChatMessageRepository;
import com.shop.chat.service.ChatService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
@CrossOrigin(origins = "*", allowedHeaders = "*", methods = {RequestMethod.GET, RequestMethod.POST, RequestMethod.DELETE, RequestMethod.OPTIONS})
public class ChatController {

    @Autowired
    private ChatService chatService;
    
    @Autowired
    private ChatMessageRepository chatMessageRepository;

    @PostMapping
    public ResponseEntity<Map<String, Object>> chat(@RequestBody Object input) {
        Map<String, Object> response = new HashMap<>();
        
        try {
            String message;
            
            // Xử lý input có thể là String hoặc Map
            if (input instanceof String) {
                message = (String) input;
            } else if (input instanceof Map) {
                Map<?, ?> messageMap = (Map<?, ?>) input;
                if (messageMap.containsKey("message")) {
                    message = messageMap.get("message").toString();
                } else {
                    message = input.toString();
                }
            } else {
                message = input.toString();
            }
            
            System.out.println("Received message: " + message);
            
            // Gọi Gemini API để lấy phản hồi
            String aiResponse = chatService.chatWithGemini(message);
            System.out.println("AI Response: " + aiResponse);
            
            // Lưu tin nhắn vào MongoDB
            ChatMessage chatMessage = new ChatMessage(message, aiResponse);
            chatMessageRepository.save(chatMessage);
            System.out.println("Message saved to database");
            
            // Trả về response với nhiều format để frontend có thể xử lý
            response.put("success", true);
            response.put("reply", aiResponse);
            response.put("assistantResponse", aiResponse);
            response.put("message", aiResponse);
            
            System.out.println("Sending response: " + response);
            
            // Xóa tất cả manual CORS headers - để Gateway xử lý
            return ResponseEntity.ok()
                .header("Content-Type", "application/json")
                .body(response);
                
        } catch (Exception e) {
            System.err.println("Error in chat endpoint: " + e.getMessage());
            e.printStackTrace();
            
            response.put("success", false);
            response.put("error", true);
            response.put("message", "Lỗi xử lý tin nhắn: " + e.getMessage());
            response.put("reply", "Xin lỗi, có lỗi xảy ra khi xử lý tin nhắn của bạn.");
            
            return ResponseEntity.status(500)
                .header("Content-Type", "application/json")
                .body(response);
        }
    }
    
    // Xóa OPTIONS handler - Gateway sẽ xử lý
    
    @GetMapping
    public ResponseEntity<List<Map<String, String>>> getMessages() {
        try {
            List<ChatMessage> chatHistory = chatMessageRepository.findTop10ByOrderByTimestampDesc();
            List<Map<String, String>> formattedHistory = new ArrayList<>();
            
            // Đảo ngược thứ tự để hiển thị từ cũ đến mới
            for (int i = chatHistory.size() - 1; i >= 0; i--) {
                ChatMessage message = chatHistory.get(i);
                
                // Thêm tin nhắn người dùng
                Map<String, String> userMessage = new HashMap<>();
                userMessage.put("from", "user");
                userMessage.put("text", message.getUserMessage());
                formattedHistory.add(userMessage);
                
                // Thêm phản hồi từ bot
                Map<String, String> botMessage = new HashMap<>();
                botMessage.put("from", "bot");
                botMessage.put("text", message.getAssistantResponse());
                formattedHistory.add(botMessage);
            }
            
            System.out.println("Returning " + formattedHistory.size() + " messages");
            return ResponseEntity.ok()
                .header("Content-Type", "application/json")
                .body(formattedHistory);
                
        } catch (Exception e) {
            System.err.println("Error getting messages: " + e.getMessage());
            return ResponseEntity.ok(new ArrayList<>());
        }
    }
    
    @DeleteMapping
    public ResponseEntity<Map<String, Object>> clearMessages() {
        try {
            chatMessageRepository.deleteAll();
            
            Map<String, Object> response = new HashMap<>();
            response.put("success", true);
            response.put("message", "Chat history cleared successfully");
            
            return ResponseEntity.ok()
                .header("Content-Type", "application/json")
                .body(response);
                
        } catch (Exception e) {
            Map<String, Object> response = new HashMap<>();
            response.put("success", false);
            response.put("error", e.getMessage());
            
            return ResponseEntity.status(500)
                .header("Content-Type", "application/json")
                .body(response);
        }
    }
}