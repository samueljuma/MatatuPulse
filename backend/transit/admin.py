from django.contrib import admin

from .models import Route, RouteSacco, RouteStage, Stage


class RouteStageInline(admin.TabularInline):
    model = RouteStage
    extra = 0


class RouteSaccoInline(admin.TabularInline):
    model = RouteSacco
    extra = 0


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "via")
    inlines = [RouteStageInline, RouteSaccoInline]


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("name", "aliases")
