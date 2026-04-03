All template tags in django_component, like `{% component %}` or `{% slot %}`, and so on,
support extra syntax that makes it possible to write components like in Vue or React (JSX).

## Self-closing tags

When you have a tag like `{% component %}` or `{% slot %}`, but it has no content, you can simply append a forward slash `/` at the end, instead of writing out the closing tags like `{% endcomponent %}` or `{% endslot %}`:

So this:

```django
{% component "button" %}{% endcomponent %}
```

becomes

```django
{% component "button" / %}
```

## Special characters

_New in version 0.71_:

Keyword arguments can contain special characters `# @ . - _`, so keywords like
so are still valid:

```django
<body>
    {% component "calendar" my-date="2015-06-19" @click.native=do_something #some_id=True / %}
</body>
```

These can then be accessed inside `get_template_data` so:

```py
@register("calendar")
class Calendar(Component):
    def get_template_data(self, args, kwargs, slots, context):
        return {
            "date": kwargs["my-date"],
            "id": kwargs["#some_id"],
            "on_click": kwargs["@click.native"]
        }
```

## Pass dictonary by its key-value pairs

_New in version 0.74_:

Sometimes, a component may expect a dictionary as one of its inputs.

Most commonly, this happens when a component accepts a dictionary
of HTML attributes (usually called `attrs`) to pass to the underlying template.

In such cases, we may want to define some HTML attributes statically, and other dynamically.
But for that, we need to define this dictionary on Python side:

```djc_py
@register("my_comp")
class MyComp(Component):
    template = """
        {% component "other" attrs=attrs / %}
    """

    def get_template_data(self, args, kwargs, slots, context):
        attrs = {
            "class": "pa-4 flex",
            "data-some-id": kwargs["some_id"],
            "@click.stop": "onClickHandler",
        }
        return {"attrs": attrs}
```

But as you can see in the case above, the event handler `@click.stop` and styling `pa-4 flex`
are disconnected from the template. If the component grew in size and we moved the HTML
to a separate file, we would have hard time reasoning about the component's template.

Luckily, there's a better way.

When we want to pass a dictionary to a component, we can define individual key-value pairs
as component kwargs, so we can keep all the relevant information in the template. For that,
we prefix the key with the name of the dict and `:`. So key `class` of input `attrs` becomes
`attrs:class`. And our example becomes:

```djc_py
@register("my_comp")
class MyComp(Component):
    template = """
        {% component "other"
            attrs:class="pa-4 flex"
            attrs:data-some-id=some_id
            attrs:@click.stop="onClickHandler"
        / %}
    """

    def get_template_data(self, args, kwargs, slots, context):
        return {"some_id": kwargs["some_id"]}
```

Sweet! Now all the relevant HTML is inside the template, and we can move it to a separate file with confidence:

```django
{% component "other"
    attrs:class="pa-4 flex"
    attrs:data-some-id=some_id
    attrs:@click.stop="onClickHandler"
/ %}
```

> Note: It is NOT possible to define nested dictionaries, so
> `attrs:my_key:two=2` would be interpreted as:
>
> ```py
> {"attrs": {"my_key:two": 2}}
> ```

## Multiline tags

By default, Django expects a template tag to be defined on a single line.

However, this can become unwieldy if you have a component with a lot of inputs:

```django
{% component "card" title="Joanne Arc" subtitle="Head of Kitty Relations" date_last_active="2024-09-03" ... %}
```

Instead, when you install django_components_lite, it automatically configures Django
to suport multi-line tags.

So we can rewrite the above as:

```django
{% component "card"
    title="Joanne Arc"
    subtitle="Head of Kitty Relations"
    date_last_active="2024-09-03"
    ...
%}
```

Much better!

To disable this behavior, set [`COMPONENTS.multiline_tag`](#multiline_tags---enabledisable-multiline-support) to `False`
