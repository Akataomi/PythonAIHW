import requests

class NutritionAPI:
    def __init__(self):
        self.base_url = "https://world.openfoodfacts.org/cgi/search.pl"
    
    def search_product(self, product_name):
        """Ищет продукт в OpenFoodFacts и возвращает калорийность на 100г"""
        params = {
            'action': 'process',
            'search_terms': product_name,
            'json': 'true',
            'page_size': 5
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            products = data.get('products', [])
            for product in products:
                nutriments = product.get('nutriments', {})
                calories = nutriments.get('energy-kcal_100g') or nutriments.get('energy_100g', 0) / 4.184
                
                if calories and product.get('product_name'):
                    return {
                        'name': product['product_name'],
                        'calories_per_100g': round(calories, 1),
                        'image_url': product.get('image_front_url', '')
                    }
            return None
        except requests.RequestException as e:
            print(f"Ошибка поиска продукта: {e}")
            return None