package com.shop.orderservice.configs;

import com.shop.orderservice.utils.JwtFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * @author SatyaRajAwasth1
 * Written on: 5/16/2023
 * @project shopping-cart-micro-services
 * A filter configuration
 */
@Configuration
public class FilterConfig {
    @Bean
    public FilterRegistrationBean jwtFilter(@Value("${jwt.secret}") String jwtSecret) {
        FilterRegistrationBean filter= new FilterRegistrationBean();
        filter.setFilter(new JwtFilter(jwtSecret));
        // endpoints that needs to be restricted.
        // All Endpoints would be restricted if unspecified
        filter.addUrlPatterns("/api/payment/*");

        return filter;
    }
}