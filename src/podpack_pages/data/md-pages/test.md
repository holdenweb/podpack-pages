This indicates quite well why the majority of the control is achieved
in the early part of the potentiometer travel. In the first 50 degrees
the voltage reading changes by 350+ units, (7 units per degree) while
the remaining 220 degrees change it less than 150 (roughly 2/3 unit
per degree of travel).

Clearly any solution that decreases the non-linearity will be of
assistance, and so lower values of \(R_v\) should be preferred.

This conflicts with the desire for a large input range, and effectively
reduces the resolution of the current light demand, because the
minimum output is fixed by the ratio of  \(R_1\) to \(R_v + R_2\) and
larger values of \(R_v\) produce higher output voltages.

Expressing the voltage \(y\) as a function of \(x\), the angle of
rotation, we have

$$\begin{align}y &= \frac{R_2+R_v x}{R_1 + R_2 + R_v x}\\y (R_1 + R_2 + R_v x) &= (R_2 + R_v x)\\y R_1 + y R_2 + y R_v x &= R_2 + R_v x\\y R_v x - R_v x &= R_2  - yR_2 - yR_1\\(y-1)R_v x &= R_2  - y (R_2 - R_1)\\x &= \frac {R_2  - y (R_2 - R_1)}{(y - 1)R_v}\end{align}$$

and, of course
there are code blocks
available just for the
writing, making it easy
to share your code.

    :::python
    @app.route("/pages/<name>")
    def page_from_html(name):
        "Serve an HTML page selected by name."
        with open(os.path.join(appfile_dir, "html-pages", f"{name}.html")) as f:
            return render_template("base.html", content=f.read())
