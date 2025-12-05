package com.shop.orderservice.services;

import com.shop.orderservice.documents.Order;
import com.shop.orderservice.enums.OrderStatus;
import com.shop.orderservice.exceptions.OrderNoFoundException;
import com.shop.orderservice.repositories.OrderRepository;
import com.shop.orderservice.resources.OrderRequest;
import com.shop.orderservice.resources.OrderResponse;
import com.shop.orderservice.resources.PaymentRequest;
import com.shop.orderservice.resources.PaymentResponse;
import com.shop.orderservice.resources.ProductResponse;
import com.shop.orderservice.enums.PaymentMode;
import com.shop.orderservice.enums.PaymentStatus;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Objects;
import java.util.logging.Logger;

@Service
public class OrderServiceImpl implements OrderService {

    Logger log = Logger.getLogger("OrderServiceImpl.class");
    private final OrderRepository orderRepository;

    @Autowired
    public OrderServiceImpl(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    @Override
    public String placeOrder(OrderRequest orderRequest, String authorizationToken) {
        log.fine("Creating order (fully mock payment) for productId: " + orderRequest.getProductId());

        float amount = orderRequest.getTotalAmount() > 0.0f ? orderRequest.getTotalAmount() : 100.0f;

        Order order = Order.builder()
                .orderDate(Instant.now())
                .amount(amount)
                .quantity(orderRequest.getQuantity())
                .productId(orderRequest.getProductId())
                .orderStatus(OrderStatus.PLACED) // trả luôn PLACED vì payment mock success
                .deliveryAddress(orderRequest.getDeliveryAddress())
                .build();

        order = orderRepository.save(order);

        // trả luôn PaymentResponse mock
        PaymentRequest paymentRequest = PaymentRequest.builder()
                .orderId(order.getId())
                .paymentMode(orderRequest.getPaymentMode() != null ? orderRequest.getPaymentMode() : PaymentMode.CASH_ON_DELIVERY)
                .amount(amount)
                .build();

        PaymentResponse paymentResponse = mockPayment(paymentRequest);

        log.fine("Order placed (mock) id=" + order.getId() + ", paymentId=" + paymentResponse.getPaymentId());

        return order.getId();
    }

    @Override
    public OrderResponse getOrderDetails(String orderId, String authorizationToken) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new OrderNoFoundException("Order not found for id: " + orderId));

        // mock product
        ProductResponse productResponse = ProductResponse.builder()
                .productId(order.getProductId())
                .productName("Mock Product")
                .quantity(order.getQuantity())
                .price(order.getAmount())
                .build();

        // mock payment
        PaymentRequest paymentRequest = PaymentRequest.builder()
                .orderId(order.getId())
                .amount(order.getAmount())
                .paymentMode(PaymentMode.CASH_ON_DELIVERY)
                .build();

        PaymentResponse paymentResponse = mockPayment(paymentRequest);

        OrderResponse.ProductDetails productDetails = OrderResponse.ProductDetails.builder()
                .productId(productResponse.getProductId())
                .productName(productResponse.getProductName())
                .quantity(productResponse.getQuantity())
                .price(productResponse.getPrice())
                .build();

        OrderResponse.PaymentDetails paymentDetails = OrderResponse.PaymentDetails.builder()
                .paymentId(paymentResponse.getPaymentId())
                .paymentStatus(PaymentStatus.valueOf(paymentResponse.getStatus()))
                .paymentDate(paymentResponse.getPaymentDate())
                .paymentMode(paymentResponse.getPaymentMode())
                .build();

        return OrderResponse.builder()
                .orderId(order.getId())
                .orderStatus(order.getOrderStatus())
                .amount(order.getAmount())
                .orderDate(order.getOrderDate())
                .productDetails(productDetails)
                .paymentDetails(paymentDetails)
                .build();
    }

    // mock payment trả ngay SUCCESS, cực nhanh
    private PaymentResponse mockPayment(PaymentRequest request) {
        return PaymentResponse.builder()
                .paymentId(System.currentTimeMillis())
                .status(PaymentStatus.SUCCESS.name())
                .paymentMode(request.getPaymentMode())
                .amount(request.getAmount())
                .paymentDate(Instant.now())
                .orderId(request.getOrderId())
                .build();
    }
}
