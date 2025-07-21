package com.shop.paymentservice.resources;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Builder;
import lombok.Getter;
import lombok.Setter;
import com.shop.paymentservice.enums.PaymentMode;
import com.shop.paymentservice.enums.PaymentStatus;

import java.io.Serializable;
import java.time.Instant;

/**
 * @author SatyaRajAwasth1
 * Written on: 5/9/2023
 * @project paymentservice
 * Resource DTO class for using as a payload for transaction responses
 */

@Setter
@Getter
@Builder
@JsonIgnoreProperties
public class PaymentResponse implements Serializable {
    private long paymentId;
    private PaymentStatus status;
    private PaymentMode paymentMode;
    private float amount;
    private Instant paymentDate;
    private String orderId;
}
