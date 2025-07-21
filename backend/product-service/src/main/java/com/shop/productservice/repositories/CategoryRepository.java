package com.shop.productservice.repositories;

import com.shop.productservice.entities.Category;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * @author SatyaRajAwasth1
 * Written on: 6/5/2023
 * @project shopping-cart-micro-services
 * A repository / DAO for product categories
 */
public interface CategoryRepository extends JpaRepository<Category, Short> {
     Category findCategoryByName(String name);
}
