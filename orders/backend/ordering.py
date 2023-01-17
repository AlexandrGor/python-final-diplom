from rest_framework.filters import OrderingFilter
from backend.models import *
from django.db.models import Prefetch

class ProductOrdering(OrderingFilter): #custom ordering #сортировка связанной таблицы ProductInfo по её параметрам
    def filter_queryset(self, request, queryset, view):
        """
        Return a filtered queryset.
        """
        ordering = self.get_ordering(request, queryset, view)
        if ordering:
            #параметры модели ProductInfo
            product_info_ordering = [value for value in ordering if value in ['price', '-price', 'created_at', '-created_at']]
            if product_info_ordering:
                ordering = [value for value in ordering if value not in product_info_ordering]
                queryset = Product.objects.prefetch_related(Prefetch
                                ('courses', queryset=ProductInfo.objects.order_by(*product_info_ordering)))
            if ordering: #сортировка Product по оставшимся значениям
                return queryset.order_by(*ordering)
        return queryset