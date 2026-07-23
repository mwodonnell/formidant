from django.urls import path

from demo import orders, signup

urlpatterns = [
    path("", signup.signup, name="signup"),
    path("welcome/", signup.welcome, name="welcome"),
    path("orders/", orders.order_editor, name="orders"),
    path("orders/row/", orders.order_row, name="order-row"),
    path("orders/row/remove/", orders.order_row_remove, name="order-row-remove"),
]
