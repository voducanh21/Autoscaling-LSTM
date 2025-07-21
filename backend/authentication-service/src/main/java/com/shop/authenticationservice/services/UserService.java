package com.shop.authenticationservice.services;

import com.shop.authenticationservice.exceptions.UserNotFoundException;
import com.shop.authenticationservice.model.User;

/**
 * @author SatyaRajAwasth1
 * Written on: 5/16/2023
 * @project shopping-cart-micro-services
 * An interface for user services
 */
public interface UserService {
    public void saveUser(User user);
    public User getUserByEmailAndPassword(String email, String password) throws UserNotFoundException;
}
