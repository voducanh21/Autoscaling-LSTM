package com.shop.chatservice.service;

import com.shop.chatservice.model.ChatMessage;
import com.shop.chatservice.repository.ChatMessageRepository;
import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.ClassicHttpResponse;
import org.apache.hc.core5.http.io.entity.StringEntity;
import org.apache.hc.core5.http.io.entity.EntityUtils;
import org.apache.hc.core5.http.ContentType;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ChatService {

    @Autowired
    private ChatMessageRepository chatMessageRepository;

    @Value("${gemini.api-key}")
    private String apiKey;

    @Value("${gemini.model}")
    private String model;

    public String chatWithGemini(String userId, String message) {
        String url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + apiKey;

        String systemPrompt = "You are a consultant at AnD Shop. Your task is to advise customers on finding the right electronic products to meet their needs.";

        String fullMessage = systemPrompt + "\n\nCustomer: " + message;

        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            HttpPost request = new HttpPost(url);

            // Create JSON body according to Gemini API format
            JSONObject part = new JSONObject();
            part.put("text", fullMessage);
            JSONArray parts = new JSONArray();
            parts.put(part);
            JSONObject content = new JSONObject();
            content.put("parts", parts);
            JSONArray contents = new JSONArray();
            contents.put(content);
            JSONObject body = new JSONObject();
            body.put("contents", contents);

            // Create StringEntity with the correct ContentType
            StringEntity entity = new StringEntity(body.toString(), ContentType.APPLICATION_JSON);
            request.setEntity(entity);
            request.setHeader("Content-Type", "application/json");

            // Send request
            try (ClassicHttpResponse response = httpClient.execute(request)) {
                String responseBody = EntityUtils.toString(response.getEntity());
                JSONObject jsonResponse = new JSONObject(responseBody);

                // Check if the response has "candidates"
                if (!jsonResponse.has("candidates")) {
                    return "Gemini API response missing 'candidates': " + responseBody;
                }
                JSONArray candidates = jsonResponse.getJSONArray("candidates");
                if (candidates.isEmpty()) {
                    return "Gemini API response has empty 'candidates': " + responseBody;
                }
                JSONObject firstCandidate = candidates.getJSONObject(0);
                if (!firstCandidate.has("content")) {
                    return "Gemini API candidate missing 'content': " + responseBody;
                }
                JSONObject contentObj = firstCandidate.getJSONObject("content");
                if (!contentObj.has("parts")) {
                    return "Gemini API content missing 'parts': " + responseBody;
                }
                JSONArray partsArr = contentObj.getJSONArray("parts");
                if (partsArr.isEmpty()) {
                    return "Gemini API parts is empty: " + responseBody;
                }
                JSONObject firstPart = partsArr.getJSONObject(0);
                if (!firstPart.has("text")) {
                    return "Gemini API part missing 'text': " + responseBody;
                }
                String assistantResponse = firstPart.getString("text");

                // Save the message to the database
                saveMessage(userId, message, assistantResponse);

                return assistantResponse;
            }
        } catch (Exception e) {
            e.printStackTrace();
            return "Error calling Gemini API: " + e.getMessage();
        }
    }

    public void saveMessage(String userId, String userMessage, String assistantResponse) {
        ChatMessage chatMessage = new ChatMessage(userId, userMessage, assistantResponse);
        chatMessageRepository.save(chatMessage);
    }

    public List<ChatMessage> getChatHistory(String userId) {
        return chatMessageRepository.findByUserIdOrderByTimestampDesc(userId);
    }

    public void clearChatHistory(String userId) {
        List<ChatMessage> messages = chatMessageRepository.findByUserIdOrderByTimestampDesc(userId);
        chatMessageRepository.deleteAll(messages);
    }
}