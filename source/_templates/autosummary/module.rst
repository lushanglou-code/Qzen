{# Custom template for autosummary to generate detailed module pages #}

{{ fullname | escape | underline }}

.. automodule:: {{ fullname }}
   :members:

   {% block functions %}
   {% if functions %}
   .. rubric:: 函数

   .. autosummary::
      :toctree:

      {% for item in functions %}
      {{ item }}
      {% endfor %}
   {% endif %}
   {% endblock %}

   {% block classes %}
   {% if classes %}
   .. rubric:: 类

   .. autosummary::
      :toctree:

      {% for item in classes %}
      {{ item }}
      {% endfor %}
   {% endif %}
   {% endblock %}