{# Custom template for module pages - Final version #}
{{ fullname | escape | underline }}

.. automodule:: {{ fullname }}
    :no-members:

{% if functions %}
.. rubric:: Functions

.. autosummary::
   :toctree:
   :template: function.rst

   {% for item in functions %}
      {{ item }}
   {%- endfor %}
{% endif %}

{% if classes %}
.. rubric:: Classes

.. autosummary::
   :toctree:
   :template: class.rst

   {% for item in classes %}
      {{ item }}
   {%- endfor %}
{% endif %}

{% if exceptions %}
.. rubric:: Exceptions

.. autosummary::
   :toctree:
   :template: exception.rst

   {% for item in exceptions %}
      {{ item }}
   {%- endfor %}
{% endif %}
