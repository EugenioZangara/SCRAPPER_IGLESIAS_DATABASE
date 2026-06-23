"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from apps.iglesias import views as iglesias_views

handler403 = 'apps.iglesias.views.error_403'
handler404 = 'apps.iglesias.views.error_404'
handler500 = 'apps.iglesias.views.error_500'

urlpatterns = [
    path('', include('apps.iglesias.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('sitemap.xml', iglesias_views.sitemap, name='sitemap'),
    path('robots.txt', iglesias_views.robots_txt, name='robots_txt'),
    path('ads.txt', iglesias_views.ads_txt, name='ads_txt'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    re_path(r'^imagenes-parroquias/(?P<path>.*)$', serve, {
        'document_root': str(settings.BASE_DIR / 'imagenes_parroquias'),
    }),
]
