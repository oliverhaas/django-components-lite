Next we will add CSS and JavaScript to our template.

!!! info

    In django-components, using JS and CSS is as simple as defining them on the Component class.
    JS and CSS files are served via Django's static files system, and `<link>` / `<script>` tags
    are automatically prepended to each component's rendered HTML.

### 1. Update project structure

Start by creating empty `calendar.js` and `calendar.css` files:

```
sampleproject/
├── calendarapp/
├── components/
│   └── calendar/
│       ├── calendar.py
│       ├── calendar.js       🆕
│       ├── calendar.css      🆕
│       └── calendar.html
├── sampleproject/
├── manage.py
└── requirements.txt
```

### 2. Write CSS

Inside `calendar.css`, write:

```css title="[project root]/components/calendar/calendar.css"
.calendar {
  width: 200px;
  background: pink;
}
.calendar span {
  font-weight: bold;
}
```

Be sure to prefix your rules with unique CSS class like `calendar`, so the CSS doesn't clash with other rules.

<!-- TODO: UPDATE AFTER SCOPED CSS ADDED -->

!!! note

    Soon, django-components will automatically scope your CSS by default, so you won't have to worry
    about CSS class clashes.

This CSS file is served via Django's static files system. A `<link>` tag pointing to the
static file URL is prepended to the component's rendered HTML.

### 3. Write JS

Next we write a JavaScript file that specifies how to interact with this component.

You are free to use any javascript framework you want.

```js title="[project root]/components/calendar/calendar.js"
(function () {
  document.querySelector(".calendar").onclick = () => {
    alert("Clicked calendar!");
  };
})();
```

A good way to make sure the JS of this component doesn't clash with other components is to define all JS code inside
an [anonymous self-invoking function](https://developer.mozilla.org/en-US/docs/Glossary/IIFE) (`(() => { ... })()`).
This makes all variables defined only be defined inside this component and not affect other components.

<!-- TODO: UPDATE AFTER FUNCTIONS WRAPPED -->

!!! note

    Soon, django-components will automatically wrap your JS in a self-invoking function by default
    (except for JS defined with `<script type="module">`).

Similarly, the JS file is served as a static file. A `<script>` tag pointing to the
static file URL is prepended to the component's rendered HTML.

### 4. Link JS and CSS to a component

Finally, we return to our Python component in `calendar.py` to tie this together.

To link JS and CSS defined in other files, use [`js_file`](../../reference/api#django_components.Component.js_file)
and [`css_file`](../../reference/api#django_components.Component.css_file) attributes:

```python title="[project root]/components/calendar/calendar.py"
from django_components import Component

class Calendar(Component):
    template_file = "calendar.html"
    js_file = "calendar.js"   # <--- new
    css_file = "calendar.css"   # <--- new

    def get_template_data(self, args, kwargs, slots, context):
        return {
            "date": "1970-01-01",
        }
```

And that's it! If you were to embed this component in an HTML, django-components will
automatically embed the associated JS and CSS.

!!! note

    Similarly to the template file, the JS and CSS file paths can be either:

    1. Relative to the Python component file (as seen above),
    2. Relative to any of the component directories as defined by
    [`COMPONENTS.dirs`](../../reference/settings#django_components.app_settings.ComponentsSettings.dirs)
    and/or [`COMPONENTS.app_dirs`](../../reference/settings#django_components.app_settings.ComponentsSettings.app_dirs)
    (e.g. `[your apps]/components` dir and `[project root]/components`)
    3. Relative to any of the directories defined by `STATICFILES_DIRS`.

---

Now that we have a fully-defined component, [next let's use it in a Django template ➡️](./components_in_templates.md).
