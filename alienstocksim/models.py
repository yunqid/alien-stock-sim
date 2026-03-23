from django.db import models
from django.contrib.auth.models import User

class NewsItem(models.Model):
    company = models.CharField(max_length = 200) #maybe a foreignkey? Then we would need a company model
    headline = models.CharField(max_length = 200)
    blurb = models.CharField(max_length = 200, default="")
    direction = models.CharField(max_length = 200, default="")
    severity = models.IntegerField(default = 1)
    #1 is least severe
    #2 is medium
    #3 is significant news


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete = models.PROTECT)
    followers = models.ManyToManyField("self", 
                                       symmetrical = False, 
                                       related_name = "following",
                                       blank = True)
    liquid_money = models.IntegerField(default = 10000) #everyone starts with $10,000


class StockEntry(models.Model): 
    #This model will store each entry of a users stock holdings
    profile = models.ForeignKey(Profile,
                                on_delete = models.PROTECT,
                                related_name = "stocks")
    company = models.CharField(max_length = 200)
    quantity = models.IntegerField(default = 0)
    # Whole dollars paid for shares still held (updated on buy/sell in trade_stock).
    cost_basis_paid = models.IntegerField(default = 0)

    class Meta:
        #This meta class is important because it prevents duplicate entries
        #i.e. (Leyu, "CMPA") can't be created if ("Leyu", "CMPA") already exists in DB
        unique_together = ("profile", "company")

        #To get a stock and its quantity from a user, do
        #holding, created = StockEntry.get_or_create(profile=profile, company = "<company>")
        #holding.quantity += <new amount bought>
        #holding.save() <-- important to save the new amount to DB