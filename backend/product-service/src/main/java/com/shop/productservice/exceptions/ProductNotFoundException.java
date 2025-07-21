package com.shop.productservice.exceptions;

/**
 * @author Thinkpad on 5/9/2023
 * @project productservice
 * Custom Exception class for Product Not Found
 */
public class ProductNotFoundException extends RuntimeException {
    public ProductNotFoundException(String exceptionMessage) {
        super(exceptionMessage);
    }

}
