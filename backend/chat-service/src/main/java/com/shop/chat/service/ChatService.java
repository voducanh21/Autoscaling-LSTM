package com.shop.chat.service;

import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.ClassicHttpResponse;
import org.apache.hc.core5.http.io.entity.StringEntity;
import org.apache.hc.core5.http.io.entity.EntityUtils;
import org.apache.hc.core5.http.ContentType;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class ChatService {

    @Value("${gemini.api-key}")
    private String apiKey;

    @Value("${gemini.model}")
    private String model;

    public String chatWithGemini(String message) {
        String url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + apiKey;

        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            HttpPost request = new HttpPost(url);

            // Tạo JSON body theo định dạng của Gemini API
            JSONObject part = new JSONObject();
            part.put("text", message);
            JSONArray parts = new JSONArray();
            parts.put(part);
            JSONObject content = new JSONObject();
            content.put("parts", parts);
            JSONArray contents = new JSONArray();
            contents.put(content);
            JSONObject body = new JSONObject();
            body.put("contents", contents);

            // Tạo StringEntity với đúng ContentType
            StringEntity entity = new StringEntity(body.toString(), ContentType.APPLICATION_JSON);
            request.setEntity(entity);
            request.setHeader("Content-Type", "application/json");

            // Gửi request
            try (ClassicHttpResponse response = httpClient.execute(request)) {
                String responseBody = EntityUtils.toString(response.getEntity());
                JSONObject jsonResponse = new JSONObject(responseBody);

                // Kiểm tra response có trường "candidates" không
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
                return firstPart.getString("text");
            }
        } catch (Exception e) {
            e.printStackTrace();
            return "Error calling Gemini API: " + e.getMessage();
        }
    }
}