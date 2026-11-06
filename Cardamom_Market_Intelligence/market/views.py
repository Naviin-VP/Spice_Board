from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Avg, Max, Count, Q
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from decimal import Decimal, InvalidOperation

from .models import AuctionPrice


def _get_filters(request, include_search=False):
    """Build a safe, reusable queryset from dashboard query-string filters."""
    queryset = AuctionPrice.objects.all()

    market = request.GET.get("market", "").strip()
    cardamom_type = request.GET.get("cardamom_type", "").strip()
    start_date_value = request.GET.get("start_date", "").strip()
    end_date_value = request.GET.get("end_date", "").strip()
    min_price_value = request.GET.get("min_price", "").strip()
    max_price_value = request.GET.get("max_price", "").strip()

    if market:
        queryset = queryset.filter(market=market)
    if cardamom_type:
        queryset = queryset.filter(cardamom_type=cardamom_type)

    start_date = parse_date(start_date_value) if start_date_value else None
    end_date = parse_date(end_date_value) if end_date_value else None

    if start_date_value and not start_date:
        return None, "Invalid start date. Use YYYY-MM-DD."
    if end_date_value and not end_date:
        return None, "Invalid end date. Use YYYY-MM-DD."
    if start_date and end_date and start_date > end_date:
        return None, "Start date cannot be after end date."

    if start_date:
        queryset = queryset.filter(auction_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(auction_date__lte=end_date)

    try:
        min_price = Decimal(min_price_value) if min_price_value else None
        max_price = Decimal(max_price_value) if max_price_value else None
    except InvalidOperation:
        return None, "Price filters must be valid numbers."

    if min_price is not None and min_price < 0:
        return None, "Minimum price cannot be negative."
    if max_price is not None and max_price < 0:
        return None, "Maximum price cannot be negative."
    if min_price is not None and max_price is not None and min_price > max_price:
        return None, "Minimum price cannot be greater than maximum price."

    if min_price is not None:
        queryset = queryset.filter(price_per_kg__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(price_per_kg__lte=max_price)

    if include_search:
        search = request.GET.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(market__icontains=search) |
                Q(cardamom_type__icontains=search)
            )

    return queryset, None


def dashboard(request):
    markets = list(
        AuctionPrice.objects.exclude(market__isnull=True)
        .exclude(market__exact="").order_by()
        .values_list("market", flat=True).distinct()
    )
    cardamom_types = list(
        AuctionPrice.objects.exclude(cardamom_type__isnull=True)
        .exclude(cardamom_type__exact="").order_by()
        .values_list("cardamom_type", flat=True).distinct()
    )
    total_records = AuctionPrice.objects.count()
    latest_date = AuctionPrice.objects.aggregate(latest=Max("auction_date"))["latest"]
    average_price = AuctionPrice.objects.aggregate(average=Avg("price_per_kg"))["average"]

    return render(request, "market/dashboard.html", {
        "total_records": total_records,
        "markets": markets,
        "market_count": len(markets),
        "cardamom_types": cardamom_types,
        "latest_date": latest_date,
        "average_price": average_price,
    })


def auction_data_api(request):
    queryset, error = _get_filters(request)
    if error:
        return JsonResponse({"error": error}, status=400)

    price_queryset = queryset.filter(
        auction_date__isnull=False,
        price_per_kg__isnull=False,
    )

    total_records = queryset.count()
    market_count = queryset.exclude(market__isnull=True).exclude(market__exact="") \
        .order_by().values_list("market", flat=True).distinct().count()
    latest_date = price_queryset.aggregate(latest=Max("auction_date"))["latest"]
    average_price = price_queryset.aggregate(average=Avg("price_per_kg"))["average"]

    historical_prices = list(
        price_queryset.values("auction_date")
        .annotate(avg_price=Avg("price_per_kg"), records_count=Count("id"))
        .order_by("auction_date")
    )
    chart_data = [{
        "date": item["auction_date"].strftime("%d %b %Y"),
        "price": float(item["avg_price"]),
        "records_count": item["records_count"],
    } for item in historical_prices]

    market_history = list(
        price_queryset.exclude(market__isnull=True).exclude(market__exact="")
        .values("market", "auction_date")
        .annotate(avg_price=Avg("price_per_kg"))
        .order_by("auction_date", "market")
    )
    market_chart_data = {}
    for item in market_history:
        market_name = item["market"]
        market_chart_data.setdefault(market_name, []).append({
            "date": item["auction_date"].strftime("%d %b %Y"),
            "price": float(item["avg_price"]),
        })

    return JsonResponse({
        "total_records": total_records,
        "market_count": market_count,
        "latest_date": latest_date.strftime("%d %b %Y") if latest_date else "N/A",
        "average_price": float(average_price) if average_price is not None else None,
        "chart_data": chart_data,
        "market_chart_data": market_chart_data,
    })


def market_insights_api(request):
    queryset, error = _get_filters(request)
    if error:
        return JsonResponse({"error": error}, status=400)

    price_queryset = queryset.filter(
        auction_date__isnull=False,
        price_per_kg__isnull=False,
    )
    dates = list(
        price_queryset.order_by().values_list("auction_date", flat=True)
        .distinct().order_by("-auction_date")[:2]
    )
    if not dates:
        return JsonResponse({"has_data": False})

    latest_date = dates[0]
    previous_date = dates[1] if len(dates) > 1 else None
    latest_average = price_queryset.filter(auction_date=latest_date).aggregate(
        average=Avg("price_per_kg")
    )["average"]
    previous_average = None
    if previous_date:
        previous_average = price_queryset.filter(auction_date=previous_date).aggregate(
            average=Avg("price_per_kg")
        )["average"]

    price_change = None
    price_change_percent = None
    if latest_average is not None and previous_average is not None:
        price_change = latest_average - previous_average
        if previous_average != 0:
            price_change_percent = (price_change / previous_average) * 100

    market_rows = list(
        price_queryset.filter(auction_date=latest_date)
        .exclude(market__isnull=True).exclude(market__exact="")
        .values("market").annotate(average_price=Avg("price_per_kg"))
        .order_by("-average_price", "market")
    )
    market_ranking = [{
        "market": row["market"],
        "average_price": float(row["average_price"]),
    } for row in market_rows]
    highest_market = market_ranking[0] if market_ranking else None
    lowest_market = market_ranking[-1] if market_ranking else None

    type_rows = list(
        price_queryset.filter(auction_date=latest_date)
        .exclude(cardamom_type__isnull=True).exclude(cardamom_type__exact="")
        .values("cardamom_type").annotate(average_price=Avg("price_per_kg"))
        .order_by("-average_price", "cardamom_type")
    )
    type_comparison = [{
        "cardamom_type": row["cardamom_type"],
        "average_price": float(row["average_price"]),
    } for row in type_rows]

    type_history_rows = list(
        price_queryset.exclude(cardamom_type__isnull=True)
        .exclude(cardamom_type__exact="")
        .values("cardamom_type", "auction_date")
        .annotate(average_price=Avg("price_per_kg"))
        .order_by("auction_date", "cardamom_type")
    )
    type_history = [{
        "cardamom_type": row["cardamom_type"],
        "date": row["auction_date"].strftime("%d %b %Y"),
        "average_price": float(row["average_price"]),
    } for row in type_history_rows]

    return JsonResponse({
        "has_data": True,
        "latest_date": latest_date.strftime("%d %b %Y"),
        "previous_date": previous_date.strftime("%d %b %Y") if previous_date else None,
        "latest_average": float(latest_average) if latest_average is not None else None,
        "previous_average": float(previous_average) if previous_average is not None else None,
        "price_change": float(price_change) if price_change is not None else None,
        "price_change_percent": float(price_change_percent) if price_change_percent is not None else None,
        "highest_market": highest_market,
        "lowest_market": lowest_market,
        "market_ranking": market_ranking,
        "type_comparison": type_comparison,
        "type_history": type_history,
    })


def auction_records_api(request):
    queryset, error = _get_filters(request, include_search=True)
    if error:
        return JsonResponse({"error": error}, status=400)

    allowed_sort_fields = {"auction_date", "market", "cardamom_type", "price_per_kg"}
    sort_by = request.GET.get("sort", "auction_date")
    sort_order = request.GET.get("order", "desc")
    if sort_by not in allowed_sort_fields:
        sort_by = "auction_date"
    if sort_order not in {"asc", "desc"}:
        sort_order = "desc"
    if sort_order == "desc":
        sort_by = "-" + sort_by
    queryset = queryset.order_by(sort_by, "-id")

    try:
        page_number = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid pagination values."}, status=400)
    if page_number < 1 or page_size < 1 or page_size > 100:
        return JsonResponse({"error": "Page must be positive and page size must be between 1 and 100."}, status=400)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page_number)
    records = [{
        "id": item.id,
        "auction_date": item.auction_date.strftime("%d %b %Y") if item.auction_date else "N/A",
        "market": item.market or "N/A",
        "cardamom_type": item.cardamom_type or "N/A",
        "price_per_kg": float(item.price_per_kg) if item.price_per_kg is not None else None,
    } for item in page_obj.object_list]

    return JsonResponse({
        "records": records,
        "total_records": paginator.count,
        "current_page": page_obj.number,
        "total_pages": paginator.num_pages,
        "page_size": page_size,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    })


def _linear_fit(points):
    """Return intercept and slope for y against sequential x values."""
    n = len(points)
    if n < 2:
        return None, None
    xs = list(range(n))
    ys = [float(item["average"]) for item in points]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return y_mean, 0.0
    slope = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n)) / denominator
    return y_mean - slope * x_mean, slope


def forecast_api(request):
    queryset, error = _get_filters(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        horizon = int(request.GET.get("horizon", 7))
    except (TypeError, ValueError):
        horizon = 7
    if horizon not in (7, 15, 30):
        horizon = 7
    rows = list(queryset.filter(auction_date__isnull=False, price_per_kg__isnull=False)
        .values("auction_date").annotate(average=Avg("price_per_kg")).order_by("auction_date"))
    history = [{"date": row["auction_date"].strftime("%d %b %Y"), "price": round(float(row["average"]), 2)} for row in rows]
    if len(rows) < 5:
        return JsonResponse({"history": history, "forecast": [], "forecast_average": None, "direction": "Insufficient data", "mape": None, "note": "At least five distinct auction dates are required for this baseline forecast."})
    # Hold out the final 20% of dates to estimate out-of-sample error.
    split = max(3, int(len(rows) * 0.8))
    train = rows[:split]
    intercept, slope = _linear_fit(train)
    test_errors = []
    for idx, row in enumerate(rows[split:], start=len(train)):
        predicted = max(0.0, intercept + slope * idx)
        actual = float(row["average"])
        if actual:
            test_errors.append(abs(actual - predicted) / abs(actual) * 100)
    mape = sum(test_errors) / len(test_errors) if test_errors else None
    # Refit on all available history for future estimates.
    intercept, slope = _linear_fit(rows)
    from datetime import timedelta
    last_date = rows[-1]["auction_date"]
    forecast = []
    for day in range(1, horizon + 1):
        value = max(0.0, intercept + slope * (len(rows) - 1 + day))
        forecast.append({"date": (last_date + timedelta(days=day)).strftime("%d %b %Y"), "price": round(value, 2)})
    average = sum(x["price"] for x in forecast) / len(forecast)
    direction = "Rising" if slope > 0.01 else "Falling" if slope < -0.01 else "Sideways"
    return JsonResponse({"history": history[-180:], "forecast": forecast, "forecast_average": round(average, 2), "direction": direction, "mape": round(mape, 2) if mape is not None else None, "note": "Method: ordinary least-squares trend on sequential auction dates; latest 20% holdout MAPE is shown when test observations exist. Future calendar dates are estimates and do not imply auctions occur every day."})


def export_intelligence_api(request):
    queryset, error = _get_filters(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    base = queryset.filter(auction_date__isnull=False, price_per_kg__isnull=False)
    markets = list(base.exclude(market__isnull=True).exclude(market__exact="")
        .values_list("market", flat=True).distinct())
    result = []
    for market in markets:
        market_rows = list(base.filter(market=market).values("auction_date")
            .annotate(average=Avg("price_per_kg")).order_by("-auction_date")[:30])
        if not market_rows:
            continue
        latest = float(market_rows[0]["average"])
        previous = float(market_rows[1]["average"]) if len(market_rows) > 1 else None
        change = ((latest - previous) / previous * 100) if previous not in (None, 0) else None
        values = [float(x["average"]) for x in market_rows]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        volatility = ((variance ** 0.5) / mean * 100) if mean else None
        result.append({"market": market, "latest_date": market_rows[0]["auction_date"].strftime("%d %b %Y"), "average_price": round(latest, 2), "previous_average": round(previous, 2) if previous is not None else None, "change_percent": round(change, 2) if change is not None else None, "volatility": round(volatility, 2) if volatility is not None else None})
    result.sort(key=lambda x: x["average_price"], reverse=True)
    return JsonResponse({"markets": result, "highest": result[0] if result else None, "lowest": result[-1] if result else None, "basis": "Domestic auction records only"})



def market_analytics_api(request):
    """Heatmap, data-derived daily brief, anomaly flags and daily market spreads."""
    queryset, error = _get_filters(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    base = queryset.filter(auction_date__isnull=False, price_per_kg__isnull=False)
    daily_market = list(base.exclude(market__isnull=True).exclude(market__exact="")
        .values("market", "auction_date").annotate(average=Avg("price_per_kg"))
        .order_by("auction_date", "market"))
    if not daily_market:
        return JsonResponse({"heatmap": [], "spread": [], "anomalies": [], "report": {"paragraphs": ["No auction records match the selected filters."], "direction": "No data", "market_count": 0}})

    dates = sorted({row["auction_date"] for row in daily_market})
    latest_date = dates[-1]
    previous_date = dates[-2] if len(dates) > 1 else None
    latest_rows = [r for r in daily_market if r["auction_date"] == latest_date]
    previous_rows = [r for r in daily_market if previous_date and r["auction_date"] == previous_date]
    latest_avg = sum(float(r["average"]) for r in latest_rows) / len(latest_rows)
    previous_avg = (sum(float(r["average"]) for r in previous_rows) / len(previous_rows)) if previous_rows else None
    change_pct = ((latest_avg-previous_avg)/previous_avg*100) if previous_avg not in (None, 0) else None
    direction = "Rising" if change_pct is not None and change_pct > 0.25 else "Falling" if change_pct is not None and change_pct < -0.25 else "Stable / mixed" if change_pct is not None else "Insufficient comparison"

    # Keep the heatmap compact: up to 10 most recent auction dates and 12 markets.
    heat_dates = set(dates[-10:])
    market_names = sorted({r["market"] for r in daily_market})[:12]
    heatmap = [{"market":r["market"],"date":r["auction_date"].strftime("%d %b %y"),"average":round(float(r["average"]),2)} for r in daily_market if r["auction_date"] in heat_dates and r["market"] in market_names]

    spread=[]
    by_date={}
    for row in daily_market: by_date.setdefault(row["auction_date"],[]).append(row)
    for day, items in sorted(by_date.items()):
        if len(items)<2: continue
        high=max(items,key=lambda x:float(x["average"]))
        low=min(items,key=lambda x:float(x["average"]))
        spread.append({"date":day.strftime("%d %b %y"),"spread":round(float(high["average"])-float(low["average"]),2),"highest_market":high["market"],"lowest_market":low["market"]})

    # Flag observations >=2 standard deviations from up to seven prior daily observations for that market.
    from math import sqrt
    histories={}
    anomalies=[]
    for row in daily_market:
        market=row["market"]; value=float(row["average"]); prior=histories.setdefault(market,[])
        if len(prior)>=4:
            sample=prior[-7:]; mean=sum(sample)/len(sample); variance=sum((x-mean)**2 for x in sample)/len(sample); sd=sqrt(variance)
            if sd>0 and abs(value-mean)>=2*sd:
                anomalies.append({"market":market,"date":row["auction_date"].strftime("%d %b %Y"),"average":round(value,2),"deviation_percent":round((value-mean)/mean*100,2) if mean else 0})
        prior.append(value)
    anomalies=anomalies[-20:][::-1]

    highest=max(latest_rows,key=lambda x:float(x["average"]))
    lowest=min(latest_rows,key=lambda x:float(x["average"]))
    paragraphs=[f"Across {len(latest_rows)} markets, the latest available auction date is {latest_date.strftime('%d %b %Y')}. The unweighted average of market averages is ₹{latest_avg:,.2f} per kg."]
    if change_pct is not None:
        paragraphs.append(f"Compared with the previous available auction date, the cross-market average is {abs(change_pct):.2f}% {'higher' if change_pct>0 else 'lower' if change_pct<0 else 'unchanged'}. The overall signal is {direction.lower()}.")
    paragraphs.append(f"{highest['market']} recorded the highest market average at ₹{float(highest['average']):,.2f}/kg, while {lowest['market']} recorded the lowest at ₹{float(lowest['average']):,.2f}/kg. The observed same-day spread is ₹{float(highest['average'])-float(lowest['average']):,.2f}/kg.")
    if anomalies: paragraphs.append(f"The screening rule flagged {len(anomalies)} unusual historical movement(s). These are statistical alerts and should be checked against auction volume, grade mix and source data before decisions.")
    else: paragraphs.append("The screening rule did not flag unusual movements in the available history. This does not mean prices are risk-free.")
    paragraphs.append("This summary describes the supplied auction records only; it does not establish the cause of price changes or predict future prices.")
    return JsonResponse({"heatmap":heatmap,"spread":spread[-45:],"anomalies":anomalies,"report":{"latest_date":latest_date.strftime('%d %b %Y'),"direction":direction,"change_percent":round(change_pct,2) if change_pct is not None else None,"market_count":len(latest_rows),"paragraphs":paragraphs}})
