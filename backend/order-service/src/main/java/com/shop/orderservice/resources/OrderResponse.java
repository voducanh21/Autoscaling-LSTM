package com.shop.orderservice.resources;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import com.shop.orderservice.enums.OrderStatus;
import com.shop.orderservice.enums.PaymentMode;
import com.shop.orderservice.enums.PaymentStatus;

import java.time.Instant;

/**
 * @author SatyaRajAwasth1
 * Written on: 5/10/2023
 * @project orderservice
 * a DTO class as a resource for sending as response entity for order
 */
@Data
@Builder
public class OrderResponse {
        private String orderId;
        private Instant orderDate;
        private OrderStatus orderStatus;
        private float amount;
        private ProductDetails productDetails;
        private PaymentDetails paymentDetails;

        @Data
        @Builder
        @AllArgsConstructor
        @NoArgsConstructor
        public static class ProductDetails {

            private String productName;
            private long productId;
            private int quantity;
            private float price;
        }

        @Data
        @AllArgsConstructor
        @NoArgsConstructor
        @Builder
        public static class PaymentDetails{
            private long paymentId;
            private PaymentMode paymentMode;
            private PaymentStatus paymentStatus;
            private Instant paymentDate;
        }
}
