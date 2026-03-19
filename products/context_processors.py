from .models import Category
# Global: giúp tất cả các template đều có thể truy cập được category 
# mà không cần phải truyền vào context của từng view
def categories(request):
    return {
        'categories': Category.objects.all().order_by('name'),
    }
