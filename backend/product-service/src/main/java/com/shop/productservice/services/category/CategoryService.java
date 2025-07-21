package com.shop.productservice.services.category;

import com.shop.productservice.entities.Category;

import java.util.List;

/**
 * @author SatyaRajAwasth1
 * Written on: 6/5/2023
 * @project shopping-cart-micro-services
 * Services for product Category
 */
public interface CategoryService {
    public String[] getAllCategories();

    void addCategory(Category category);

    Category getCategoryByName(String categoryName);

}
