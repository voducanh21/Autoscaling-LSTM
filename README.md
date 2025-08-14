# E-commerce Microservices Application

A comprehensive e-commerce application built with microservices architecture using Angular frontend and Spring Boot backend services.

## 🏗️ System Architecture

### Backend (Microservices)
- **API Gateway**: Single entry point for all client requests with routing and security
- **Authentication Service**: Handles user authentication, registration, and authorization
- **Product Service**: Manages products, categories, and inventory
- **Order Service**: Processes orders and manages shopping cart functionality
- **Payment Service**: Handles payment processing and transactions
- **Chat Service**: Provides customer support chat functionality

### Frontend
- **Angular**: Single Page Application with Material Design components
- **Tailwind CSS**: Utility-first CSS framework for responsive styling

### Databases
- **MySQL**: Used by Authentication Service and Payment Service
- **PostgreSQL**: Used by Product Service for product data
- **MongoDB**: Used by Order Service and Chat Service

## 🚀 Getting Started

### System Requirements
- Node.js (v16+)
- Java 17+
- Docker & Docker Compose
- Angular CLI
- Maven

### 1. Database Setup with Docker

```bash
cd backend
docker-compose up -d
```

This command will initialize:
- MySQL (port 3306) - creates databases: `userdb`, `paymentdb`
- PostgreSQL (port 5432) - creates database: `productdb`
- MongoDB (port 27017) - databases for order and chat services

### 2. Running Backend Services

Start the services in the following order:

#### API Gateway
```bash
cd backend/api-gateway
./mvnw clean install
./mvnw spring-boot:run
```

#### Authentication Service
```bash
cd backend/authentication-service
./mvnw clean install
./mvnw spring-boot:run
```

#### Product Service
```bash
cd backend/product-service
./mvnw clean install
./mvnw spring-boot:run
```

#### Order Service
```bash
cd backend/order-service
./mvnw clean install
./mvnw spring-boot:run
```

#### Payment Service
```bash
cd backend/payment-service
./mvnw clean install
./mvnw spring-boot:run
```

#### Chat Service
```bash
cd backend/chat-service
./mvnw clean install
./mvnw spring-boot:run
```

### 3. Running Frontend

```bash
cd frontend
npm install
npm start
```

The application will be available at: `http://localhost:4200`

## 🐳 Docker Deployment

### Running the entire system with Docker

```bash
# Start databases
cd backend
docker-compose up -d

# Build and run all services
docker-compose -f docker-compose.yml -f docker-compose.services.yml up --build
```

## ☸️ Kubernetes Deployment

The project supports Kubernetes deployment:

```bash
cd backend/k8s

# Deploy infrastructure (databases)
kubectl apply -f infra/

# Deploy applications
kubectl apply -f apps/
```

### Kind (Local Kubernetes)

```bash
# Create local cluster
kind create cluster --config=k8s/kind/kind-config.yml

# Deploy
kubectl apply -f k8s/infra/
kubectl apply -f k8s/apps/
```

## 📱 Key Features

### Frontend Features
- 🛒 Shopping cart and order management
- 👤 User authentication and registration
- 🔍 Product search and filtering
- 💳 Online payment processing
- 💬 Customer support chat
- 📱 Responsive design with mobile support

### Backend Features
- 🔐 JWT Authentication & Authorization
- 🛡️ API Gateway with routing and security
- 📊 Microservices architecture with service discovery
- 🗄️ Multi-database support (MySQL, PostgreSQL, MongoDB)
- 🔄 RESTful APIs with OpenAPI documentation
- 📝 Comprehensive logging and monitoring

## 🛠️ Development

### Development Prerequisites

```bash
# Install Angular CLI
npm install -g @angular/cli

# Install Maven (or use the Maven wrapper included)
# Download from: https://maven.apache.org/
```

### Running in Development Mode

```bash
# Backend - run each service separately
cd backend/api-gateway && ./mvnw spring-boot:run
cd backend/authentication-service && ./mvnw spring-boot:run
# ... continue with other services

# Frontend - with hot reload
cd frontend
ng serve --proxy-config proxy.conf.json
```

## 📋 API Documentation

After running the services, API documentation is available at:

- API Gateway: `http://localhost:8080/swagger-ui.html`
- Authentication Service: `http://localhost:8081/swagger-ui.html`
- Product Service: `http://localhost:8082/swagger-ui.html`
- Order Service: `http://localhost:8083/swagger-ui.html`
- Payment Service: `http://localhost:8084/swagger-ui.html`
- Chat Service: `http://localhost:8085/swagger-ui.html`

## 🗂️ Project Structure

```
E-commerce_Web/
├── backend/
│   ├── api-gateway/          # API Gateway service
│   ├── authentication-service/  # User authentication
│   ├── product-service/      # Product management
│   ├── order-service/        # Order processing
│   ├── payment-service/      # Payment processing
│   ├── chat-service/         # Customer support chat
│   ├── docker/              # Database initialization scripts
│   ├── k8s/                 # Kubernetes deployment files
│   └── docker-compose.yml   # Docker services configuration
├── frontend/                 # Angular application
│   ├── src/app/
│   │   ├── authentication/   # Auth components
│   │   ├── components/       # Reusable components
│   │   ├── pages/           # Page components
│   │   └── services/        # Angular services
│   └── ...
└── README.md               # This file
```

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*Last updated: August 14, 2025*
