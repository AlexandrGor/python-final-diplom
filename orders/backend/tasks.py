from celery import shared_task
from celery.result import AsyncResult
import yaml
from backend.models import *
from django.core.mail import send_mail
import smtplib
from orders.celery import app as celery_app

def get_task(task_id: str) -> AsyncResult:
    return AsyncResult(task_id, app=celery_app)

@celery_app.task()
def do_import(data, user_email):
    try:
        data = yaml.safe_load(data)
        # созданём магазин пользователя, если не было
        shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                             user_id__email=user_email)  # shop необходимое unique значение, иначе KeyError. shop <-> user отношение 1к1, тем самым пользователь может создать или изменить только один свой магазин (чтобы под одним email был один магазин)
        # созданём категории магазина, если таких не было
        for category in data['categories']:  # categories необходимое значение, иначе KeyError.
            category_object, _ = Category.objects.get_or_create(
                name=category['name'],  # name необходимое unique значение, иначе KeyError
                defaults={'id': category.get('id')}
                # так как name категории сам по себе уникален, в передаче id нет большого смысла. Если такой категории не существует, defaults создаст её с указанным id (если id в этом случае не указано, то category.get('id') вернет None)
            )
            category_object.save()  # You can’t associate it until it’s been saved
            category_object.shops.add(shop)  # Adding a second time is OK, it will not duplicate the relation
        old_offers = ProductInfo.objects.select_related('product_id').filter(shop_id=shop.id)
        old_offers.update(is_active=False)  # Отчистка всей базы-прайса магазина перед пересозданием
        for old_offer in old_offers:
            old_offer.product_id.check_actual()  # Если по продукту нет больше предложений, то product_obj.is_active = False
        for item in data[
            'goods']:  # goods необходимое значение, иначе KeyError. Нет смысла указывать только категории магазина, если в них нет продуктов.
            # созданём продукты, если таких не было
            product, _ = Product.objects.get_or_create(name=item['name'], category_id=Category(id=item[
                'category']))  # name и category необходимые значение, иначе KeyError.     category_id= требует не id а instance https://code.djangoproject.com/ticket/13915
            # созданём базу-прайс магазина
            product_info = ProductInfo.objects.create(product_id=product,
                                                      # требуется не id, а instance https://code.djangoproject.com/ticket/13915
                                                      external_id=item['id'],
                                                      # blank=False необходимое значение, иначе KeyError
                                                      model=item.get('model'),  # blank=True  default=None
                                                      price=item['price'],
                                                      # blank=False необходимое значение, иначе KeyError
                                                      price_rrc=item['price_rrc'],
                                                      # blank=False необходимое значение, иначе KeyError
                                                      quantity=item['quantity'],
                                                      # blank=False необходимое значение, иначе KeyError
                                                      shop_id=shop)
            product.is_active = True  # включаем продукт, так как по нему появилось предложение
            product.save()
            if item.get('parameters'):  # делаем возможность не указывать параметры продукта
                for name, value in item['parameters'].items():
                    parameter_object, _ = Parameter.objects.get_or_create(
                        name=name)  # созданём тип параметра, если в базе такого нет
                    ProductParameter.objects.create(product_info_id=product_info,
                                                    parameter_id=parameter_object,
                                                    value=value)  # value необходимое значение, иначе KeyError
        return (user_email, 'Весь прайс успешно обновлен.')
    except (KeyError, Exception) as e:
        msg = f'Error: {str(e)}'
        return (user_email, msg)

@celery_app.task()
def send_email(msg, to, header='Netology homework', sender=settings.EMAIL_HOST_USER):
    try:
        send_mail(  # Заголовок
                    header,
                    # Сообщение
                    msg,
                    # Отправитель
                    sender,
                    # Получатели
                    [*to],
                    # When it’s False, send_mail() will raise an smtplib.SMTPException
                    fail_silently=False, )
    except smtplib.SMTPException as e:
        msg = f'Error: {str(e)}'
        return ('Email task', msg)
    msg = f'Письмо было успешно отправлено.' #по адресу f{" ".join(to)}
    return ('allow any', msg)