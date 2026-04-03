# Component Analytics

Use the [`Component.on_render_after()`](../../reference/api#django_components.Component.on_render_after) hook to track component analytics, such as capturing errors for a service like Sentry or other monitoring.

![Analytics example](./images/analytics.png)

## Error tracking components

You can create a wrapper component that uses the [`Component.on_render_after()`](../../reference/api#django_components.Component.on_render_after) hook to inspect the `error` object. If an error occurred during the rendering of its children, you can capture and send it to your monitoring service.

```django
{% component "sentry_error_tracker" %}
    {% component "api_widget" simulate_error=True / %}
{% endcomponent %}
```

The same hook can be used to track both successes and failures, allowing you to monitor the reliability of a component.

```django
{% component "success_rate_tracker" %}
    {% component "api_widget" simulate_error=False / %}
{% endcomponent %}
```

## Definition

```djc_py
--8<-- "docs/examples/analytics/component.py"
```

## Example

To see the component in action, you can set up a view and a URL pattern as shown below.

### `views.py`

```djc_py
--8<-- "docs/examples/analytics/page.py"
```

### `urls.py`

```python
from django.urls import path

from examples.pages.analytics import AnalyticsPage

urlpatterns = [
    path("examples/analytics", AnalyticsPage.as_view(), name="analytics"),
]
```
