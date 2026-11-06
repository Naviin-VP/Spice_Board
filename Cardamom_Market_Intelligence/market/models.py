
from django.db import models


class AuctionPrice(models.Model):
    id = models.AutoField(primary_key=True)
    production_datetime = models.DateTimeField(null=True, blank=True)
    sno = models.IntegerField(null=True, blank=True)
    auction_date = models.DateField(null=True, blank=True)
    market = models.CharField(max_length=100, null=True, blank=True)
    cardamom_type = models.CharField(max_length=50, null=True, blank=True)
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    cache_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "auction_prices"
        ordering = ["-auction_date"]

    def __str__(self):
        return f"{self.market} - {self.auction_date} - {self.price_per_kg}"
