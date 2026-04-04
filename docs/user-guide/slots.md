# Slots

Slots allow parent templates to inject content into specific areas of a component.

## Defining slots

Use `{% slot %}` in your component template:

```html
{% load component_tags %}
<div class="panel">
  <div class="panel-header">
    {% slot "header" %}Default header{% endslot %}
  </div>
  <div class="panel-body">
    {% slot "body" required %}{% endslot %}
  </div>
  <div class="panel-footer">
    {% slot "footer" %}{% endslot %}
  </div>
</div>
```

## Filling slots

Use `{% fill %}` when using the component:

```html
{% load component_tags %}
{% component "panel" %}
  {% fill "header" %}
    <h2>Custom Header</h2>
  {% endfill %}
  {% fill "body" %}
    <p>Panel content goes here.</p>
  {% endfill %}
{% endcomponent %}
```

## Default slot

Content placed directly inside `{% component %}` without a `{% fill %}` goes into the default slot:

```html
{% component "panel" %}
  This goes into the default slot.
{% endcomponent %}
```

## Slot fallback

Content inside `{% slot %}` is the fallback, rendered when no `{% fill %}` is provided:

```html
{% slot "sidebar" %}
  <p>Default sidebar content.</p>
{% endslot %}
```

## Checking if a slot is filled

In your component's template, you can check whether a slot was filled:

```html
{% load component_tags %}
{% if component_vars.slots.header %}
  <div class="has-header">
    {% slot "header" %}{% endslot %}
  </div>
{% endif %}
```
