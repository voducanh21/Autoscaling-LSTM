// filepath: d:\Ecommerce_Web\ecommerce-fullstack\backend\chat-service\src\main\java\com\shop\chat\repository\ChatMessageRepository.java
package com.shop.chat.repository;

import com.shop.chat.model.ChatMessage;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ChatMessageRepository extends MongoRepository<ChatMessage, String> {
    
    /**
     * Tìm top 10 tin nhắn mới nhất, sắp xếp theo timestamp giảm dần
     */
    List<ChatMessage> findTop10ByOrderByTimestampDesc();
    
    /**
     * Tìm top N tin nhắn mới nhất
     */
    List<ChatMessage> findTopNByOrderByTimestampDesc(int limit);
    
    /**
     * Xóa tất cả tin nhắn
     */
    void deleteAll();
}