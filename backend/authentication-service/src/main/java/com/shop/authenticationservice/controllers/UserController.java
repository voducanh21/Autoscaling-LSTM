package com.shop.authenticationservice.controllers;

import com.shop.authenticationservice.dtos.LoginRequest;
import com.shop.authenticationservice.dtos.LoginResponse;
import com.shop.authenticationservice.dtos.RegisterSuccessResponse;
import com.shop.authenticationservice.dtos.SignUpRequest;
import com.shop.authenticationservice.exceptions.UserNotFoundException;
import com.shop.authenticationservice.model.User;
import com.shop.authenticationservice.services.UserService;
import com.shop.authenticationservice.tokenutils.JwtGenerator;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * @author SatyaRajAwasth1
 * Written on: 5/15/2023
 * @project shopping-cart-micro-services
 * Controller for login and basic functionalities
 */

@RestController
@RequestMapping("api/auth")
//@CrossOrigin // no required as cross-origin is enabled on the api gateway globally
public class UserController {
    private final UserService userService;
    private final JwtGenerator jwtGenerator;
    @Autowired
    public UserController(UserService userService, JwtGenerator jwtGenerator){
        this.userService=userService;
        this.jwtGenerator=jwtGenerator;
    }

    @PostMapping("/register")
    public ResponseEntity<?> registerUser(@RequestBody SignUpRequest signUpRequest){
        try{
            User user = new User(signUpRequest.getUserName(), signUpRequest.getEmail(), signUpRequest.getPassword());
            userService.saveUser(user);
            return new ResponseEntity<>(new RegisterSuccessResponse("registration success, user username and password to login"), HttpStatus.CREATED);
        } catch (Exception e){
            return new ResponseEntity<>(e.getMessage(), HttpStatus.CONFLICT);
        }
    }

    @PostMapping("/login")
    public ResponseEntity<?> loginUser(@RequestBody LoginRequest loginRequest) {
        try {
            if(loginRequest.getEmail() == null || loginRequest.getPassword() == null) {
                throw new UserNotFoundException("Email or Password is Empty");
            }
            User user = new User();
            user.setEmail(loginRequest.getEmail());
            user.setPassword(loginRequest.getPassword());
            User userData = userService.getUserByEmailAndPassword(loginRequest.getEmail(), loginRequest.getPassword());
            if(userData == null){
                throw new UserNotFoundException("Email or Password is Invalid");
            }
            Map<String, String> tokenMap = jwtGenerator.generateToken(user);
            String token = tokenMap.get("token");
            LoginResponse loginResponse = new LoginResponse(token, userData.getUserName());
            return new ResponseEntity<>(loginResponse, HttpStatus.OK);
        } catch (UserNotFoundException e) {
            return new ResponseEntity<>(e.getMessage(), HttpStatus.CONFLICT);
        }
    }
}

