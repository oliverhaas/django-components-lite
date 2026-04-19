from django import template

register = template.Library()


@register.inclusion_tag("partials/card.html")
def card(title, body, variant, footer):
    return {"title": title, "body": body, "variant": variant, "footer": footer}


@register.inclusion_tag("partials/button.html")
def button(label, variant, size, disabled):
    return {"label": label, "variant": variant, "size": size, "disabled": disabled}


@register.inclusion_tag("partials/alert.html")
def alert(level, message, dismissible):
    return {"level": level, "message": message, "dismissible": dismissible}
