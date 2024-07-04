# Skincare Product Recommendation System

Buying new cosmetic products can be challenging and even daunting, especially for those with sensitive skin prone to skin troubles. While the essential information is on the back of each product, interpreting those ingredient lists can be tough without a background in chemistry. Instead of buying and hoping for the best, we can leverage data science to predict which products may best fit us.

# Project Overview

This project aims to help users find suitable skincare products by using the chemical components of cosmetics as the 'content' for a recommendation system. We process ingredient lists for 1,472 cosmetics from Sephora, apply word embedding techniques, visualize ingredient similarity with t-SNE, and present the results using Bokeh for interactive exploration.

# Features

Ingredient Tokenization: Splitting ingredient lists into individual tokens.
Document-Term Matrix (DTM): Creating a binary matrix representing the presence of each ingredient in each product.
t-SNE Visualization: Reducing dimensions and visualizing ingredient similarities.
Cosine Similarity: Implementing a content-based recommendation system.
Interactive Visualization: Using Bokeh to create interactive plots for easy comparison and selection of products.

# Dataset

Label: The category of the product.
Brand: The brand of the product.
Name: The name of the product.
Price: The price of the product.
Rank: The rank or rating of the product.
Ingredients: The list of ingredients in the product.
Combination, Dry, Normal, Oily, Sensitive: Columns indicating suitability for different skin types.
