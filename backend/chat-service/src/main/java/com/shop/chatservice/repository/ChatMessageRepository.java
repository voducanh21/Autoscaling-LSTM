// filepath: d:\Ecommerce_Web\ecommerce-fullstack\backend\chat-service\src\main\java\com\shop\chat\repository\ChatMessageRepository.java
package com.shop.chatservice.repository;

import com.shop.chatservice.model.ChatMessage;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ChatMessageRepository extends MongoRepository<ChatMessage, String> {
    
    /**
     * Find the top 10 newest messages, sorted by timestamp descending
     */
    List<ChatMessage> findTop10ByOrderByTimestampDesc();
    
    /**
     * Find the top N newest messages
     */
    List<ChatMessage> findTopNByOrderByTimestampDesc(int limit);

    /**
     * Find messages by userId, sorted by timestamp descending
     */
    List<ChatMessage> findByUserIdOrderByTimestampDesc(String userId);
    
    /**
     * Delete all messages
     */
    void deleteAll();
}