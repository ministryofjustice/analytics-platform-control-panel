# New templates

The templates in this directory demonstrate how to replace our old templating
systems.

The old:

* Jinja2.
* Nunjucks.
* Jinja2 emits Nunjucks emits HTML argh!
* Hacked to work in Django.
* Macros.
* Lots of code indirection (hard to debug).
* Dependencies on JavaScript.
* CSS classes annotated on most HTML tags.

The new:

* Django's built in templating system.
* A single _simple_ static CSS file ([GD.CSS](https://gdcss.netlify.app/)) for core styles.
* A single _simple_ static CSS file (`app.css`) for site specific styling.
* POSH (Plain Old Semantic HTML) templates.
* Avoidance of JavaScript both browser and server side.
* Easy to understand, debug and change.
* Boring with no surprises.

## The Story So Far

I was once asked to add a select item to one of our templates. What should have
been a 5 minute HTML edit ended up taking me a day or frustration, debugging
and misdirection.

Our old templates are a significant technical debt because:

* They are not idiomatic for the Django framework (a Django developer would look at them and ask, "what on earth..?")
* They are confusing to read (both Jinja2 and Nunjucks use the `{%` and `%}` markup, but have to be distinguished via atypical use of `{%-` and `-%}`). 
* Nunjucks pulls in a huge number of JavaScript dependencies causing dependabot overload.
* An overly modular set of dependencies between JavaScript, macros and sub-templates means we have the rediculous situation of having, say, a macro for displaying either "yes" or "no". Such massive code indirection makes it hard to figure out how the templates relate to the emitted HTML.
* Styling using the Government based CSS is class based, so the resulting HTML is heavily annotated and difficult to read.

As part of the firebreak sprint at the end of 2021 I decided to throw it all
away and start again. To this end I valued simplicity, standards, semantics and
sensible abstractions.

The result is what you see in this branch.

All that remains of the old system is found in the `jinja2` directory. As I've
rewritten our templates I've deleted the old version in `jinja2` and added the
new one in this directory.

## Hints and Tips

There are various common patterns encountered during transitioning from the old
templates to the new:

Extend `base.html`
: All the core "chrome" HTML is in the base template. You should put content in the `{% block content %} {% endblock %}` (as per usual Django templates).

The base has a header and footer
: Please see `header.html` and `footer.html` for their definition.

GD.CSS styles HTML tags and ignores divs
: This means 90% of what we do looks like "normal" government design. We are missing some design elements but these can be recreated with ease (see, for instance, how we do message handling in the `base.html`).

It's just POSH (plain old semantic HTML)
: If you're adding classes to tags, you're probably doing it wrong. Trust the defaults and put custom CSS in `app.css`.

Use Django forms
: They integrate really well (unsurprisingly). See `reset.html` for an example.

Tables are boring (and easy)
: See the `user-list.html` file for an example of how to do the AP version of tables.

Permissions work in templates too
: Make sure you `{% load rules %}` at the top of the template and then declare a flag like this example, `{% has_perm 'api.add_superuser' request.user as add_superuser %}` (where the permission to check on the current `request.user` is "api.add_superuser" and the truthy flag to be `add_superuser`), then use a standard template conditional like this: `{% if add_superuser %} ... {% endif %}`. See the `user-detail.html` template for an example of how to do this.

These examples cover all the various aspects of what we do in our templates.

## Tool List

The most important page on our site is `tool-list.html`.

Frankly, the current version is a mess.

The `tool-list.html` file _in this directory_ is an untested mock-up of what I think it could look like, as a more friendly version of the page.

Note that I have ensured the expected `id` and `class` attributes are annotated to the tags in the template so the JavaScript used to update state and ensure forms work, has the expected references.

However, I have NOT tested the updated template with JavaScript or the Django backend... what you're looking at is an afternoon's "doodle" of a "what if..?".

This template definitely needs doing properly and testing. The other templates I've converted were all relatively simple and should just work (tm).

## ToDo

* Finish conversion of all the old templates to new.
* Spend time / love on the `tool-list.html` template to revise and test it properly.
* Check the changes with actual users in a dev instance.
* Delete the `jinja2` directory and any other related files from the old world.

Best of luck..!
