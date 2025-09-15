{% extends "autosummary/module.rst" %}

{% block members %}
   .. automodule:: {{ fullname }}
      :members:
      :undoc-members:
      :no-inherited-members:
{% endblock %}
