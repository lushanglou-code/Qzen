{# Custom template for autosummary to generate detailed class pages #}

{{ fullname | escape | underline }}

.. autoclass:: {{ fullname }}
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:

   .. rubric:: 方法