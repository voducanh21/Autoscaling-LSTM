package com.shop.productservice.services.product;

import com.shop.productservice.resources.ProductRequest;
import com.shop.productservice.resources.ProductResponse;

import java.util.List;

/**
 * @author SatyaRajAwasth1 on 5/8/2023
 * A service interface for product
 */
public interface ProductService {
    long addProduct(ProductRequest productRequest);

    List<ProductResponse> getAllProducts();

    ProductResponse getProductById(long productId);

    List<ProductResponse> getProductsByCategory(String categoryName);

    void editProduct(long productId, ProductRequest productRequest);

    void deleteProductById(long productId);

    void addListOfProducts(List<ProductRequest> productRequest);
}
