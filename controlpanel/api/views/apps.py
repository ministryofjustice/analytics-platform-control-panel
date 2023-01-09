from rest_framework.generics import GenericAPIView
from rest_framework.response import Response


class AppDetailAPIView(GenericAPIView):
    permission_classes = ()
    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        app = self.get_object()
