## 1. Set up database
## Use MySQL to create database for authentication-service, payment-service
CREATE DATABASE userdb;
CREATE DATABASE paymentdb;
## Use PostgreSQL to create database for product-service
CREATE DATABASE productdb; 
## Use MongoDB to create database for order-service, chat-service


## 2. Run all service
## 2.1. Run registry-discovery-server
cd .\registry-discovery-server
.\gradlew.bat build 
## if you want to skip test
.\gradlew.bat build - test
.\gradlew bootRun
## 2.2. Run api-gateway
cd .\api-gateway
.\gradlew.bat build
.\gradlew bootRun

## 2.3. Run authentication-service
cd .\authentication-service
mvnd clean install
mvnd spring-boot:run

## 2.4. Run product-service
cd .\product-service
.\gradlew.bat build
.\gradlew bootRun

## 2.5. Run order-service
cd .\order-service
mvnd clean install
mvnd spring-boot:run

## 2.6. Run payment-service
cd .\payment-service
.\gradlew.bat build
.\gradlew bootRun

## 2.7. Run chat-service
cd .\chat-service
mvnd clean install
mvnd spring-boot:run