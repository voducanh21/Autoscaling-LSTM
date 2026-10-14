# Backend: Commerce Microservices

The backend separates the storefront API into independently runnable Spring services. A Spring Cloud Gateway provides the client entry point, while each domain service owns its API and database connection.

## Service map

| Service | Port | Responsibility | Store |
| --- | ---: | --- | --- |
| API Gateway | 8888 | Routes client `/api` traffic | — |
| Authentication | 8084 | Registration, login, and JWT issuance | MySQL (`userdb`) |
| Product | 8081 | Product catalog API | PostgreSQL (`productdb`) |
| Order | 8083 | Order API | MongoDB |
| Payment | 8082 | Payment API | MySQL (`paymentdb`) |

## Run locally

Requirements: Java 17+, Docker Compose, and the environment values below. The Maven wrapper is included in every module.

1. Supply `MYSQL_ROOT_PASSWORD`, `POSTGRES_PASSWORD`, `MONGO_INITDB_ROOT_PASSWORD`, `SPRING_DATA_MONGODB_URI`, and a shared Base64 `JWT_SECRET` of at least 256 bits through Replit Secrets or your local process environment.
2. Start the databases:

   ```bash
   docker compose -f backend/docker-compose.yml up -d mysql postgres mongodb
   ```

3. Run each service in a separate terminal:

   ```bash
   cd backend/api-gateway && ./mvnw spring-boot:run
   cd backend/authentication-service && ./mvnw spring-boot:run
   cd backend/product-service && ./mvnw spring-boot:run
   cd backend/order-service && ./mvnw spring-boot:run
   cd backend/payment-service && ./mvnw spring-boot:run
   ```

The Angular app proxies `/api` to `http://localhost:8888`; see [`../frontend/README.md`](../frontend/README.md).

## Kubernetes

From the repository root, with the required values available in the shell and a valid cluster context:

```bash
kubectl apply -f backend/k8s/infra/namespaces.yml
bash backend/k8s/infra/create-secrets.sh
kubectl apply -f backend/k8s/infra/
kubectl apply -f backend/k8s/apps/
```

Replit Secrets are not automatically delivered to an external cluster. The secret-creation script uses the current environment to create Kubernetes Secrets; apply the namespace manifests first.

## Local observability

`backend/docker-compose.yml` also defines Prometheus, Grafana, Loki, and Tempo. Start the full local dependency and observability stack with:

```bash
docker compose -f backend/docker-compose.yml up -d
```

The Compose file intentionally requires database passwords; there are no committed defaults.
