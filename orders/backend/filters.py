from django_filters import rest_framework as filters

from .models import ProductInfo, Product, Order

class ProductInfoListFilter(filters.FilterSet):
    created = filters.DateFromToRangeFilter(field_name='created_at') #?created_after=2022-05-11
    updated = filters.DateFromToRangeFilter(field_name='updated_at') #?updated_before=2022-05-11
    price = filters.RangeFilter() #?price_min=120&price_max=800
    shop = filters.CharFilter(field_name='shop_id__name', lookup_expr='icontains')  # ?shop=связной
    name = filters.CharFilter(field_name='product_id__name', lookup_expr='icontains')  #?name=iphone
    category_id = filters.NumberFilter(field_name='product_id__category_id__id', lookup_expr='exact')
    category = filters.CharFilter(field_name='product_id__category_id__name', lookup_expr='icontains')
    class Meta:
        model = ProductInfo
        fields = ['name', 'model', 'external_id', 'product_id', 'shop_id', 'shop', 'created', 'updated', 'price',
                  'category', 'category_id']

class ProductInfoFilter(filters.FilterSet):
    created = filters.DateFromToRangeFilter(field_name='created_at') #?created_after=2022-05-11
    updated = filters.DateFromToRangeFilter(field_name='updated_at') #?updated_before=2022-05-11
    price = filters.RangeFilter() #?price_min=120&price_max=800
    shop = filters.CharFilter(field_name='shop_id__name', lookup_expr='icontains')  # ?shop=связной
    class Meta:
        model = ProductInfo
        fields = ['external_id', 'shop_id', 'shop', 'created', 'updated', 'price']


class ProductFilter(filters.FilterSet):
    price = filters.RangeFilter(field_name='product_info__price', lookup_expr='exact') #?price_min=120&price_max=800
    created = filters.DateFromToRangeFilter(field_name='product_info__created_at', lookup_expr='contains')  # ?created_after=2022-05-11
    updated = filters.DateFromToRangeFilter(field_name='product_info__updated_at', lookup_expr='contains')  # ?updated_before=2022-05-11
    model = filters.CharFilter(field_name='product_info__model', lookup_expr='icontains') #?model=iphone
    shop = filters.CharFilter(field_name='product_info__shop_id__name', lookup_expr='icontains')  #?shop=связной
    shop_id = filters.NumberFilter(field_name='product_info__shop_id__id', lookup_expr='exact')  # ?shop_id=1
    category = filters.CharFilter(field_name='category_id__name', lookup_expr='icontains')  # ?category=cмартфон.. без учета регистра
    category_id = filters.Filter(field_name='category_id__id', lookup_expr='exact') # ?category_id=1
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')  # ?name=смарт
    class Meta:
        model = Product
        fields = ['name', 'category', 'category_id', 'price', 'created', 'updated', 'model', 'shop_id', 'shop']


class PartnerOrdersFilter(filters.FilterSet):
    user_email = filters.CharFilter(field_name='user_id__email', lookup_expr='icontains')
    created = filters.DateFromToRangeFilter(field_name='created_at', lookup_expr='contains')  # ?created_after=2022-05-11
    updated = filters.DateFromToRangeFilter(field_name='updated_at', lookup_expr='contains')  # ?updated_before=2022-05-11
    phone = filters.CharFilter(field_name='contact_id__phone', lookup_expr='icontains')
    city = filters.CharFilter(field_name='contact_id__city', lookup_expr='icontains')
    street = filters.CharFilter(field_name='contact_id__street', lookup_expr='icontains')
    house = filters.CharFilter(field_name='contact_id__house', lookup_expr='icontains')
    product = filters.CharFilter(field_name='ordered_items__product_info_id__product_id__name', lookup_expr='icontains') # ?product=apple
    model = filters.CharFilter(field_name='ordered_items__product_info_id__product_id__model', lookup_expr='icontains')
    class Meta:
        model = Order
        fields = ['id', 'user_email', 'status', 'created', 'updated', 'phone', 'city', 'street', 'house', 'product', 'model']