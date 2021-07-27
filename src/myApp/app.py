#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template Python module generated based on 'app_template', 'phantasy-ui'
is required to make it executable as a PyQt5 app.

Created by: makeBasePyQtApp.

An example to create an app template:

>>> makeBasePyQtApp --app my_great_app --template AppWindow

Show the available templates:

>>> makeBasePyQtApp -l
"""

import sys

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QMessageBox

from mpl4qt.widgets import MatplotlibBaseWidget

from phantasy import MachinePortal
from phantasy_ui import BaseAppForm
from phantasy_ui.widgets import ElementWidget
from phantasy_apps.allison_scanner.data import draw_beam_ellipse_with_params

from .ui.ui_app import Ui_MainWindow

MACH, SEGM = "ARIS", "F1"
ARIS_MP = MachinePortal(MACH, SEGM)
ARIS_LAT = ARIS_MP.work_lattice_conf

# key strings for Twiss X,Y parameters
TWISS_KEYS_X = [
    i.format(u='x') for i in ('{u}_cen', '{u}p_cen', '{u}_rms', '{u}p_rms',
                              'emit_{u}', 'emitn_{u}', 'alpha_{u}', 'beta_{u}',
                              'gamma_{u}', 'total_intensity')
]
TWISS_KEYS_Y = [
    i.format(u='y') for i in ('{u}_cen', '{u}p_cen', '{u}_rms', '{u}p_rms',
                              'emit_{u}', 'emitn_{u}', 'alpha_{u}', 'beta_{u}',
                              'gamma_{u}', 'total_intensity')
]


class MyAppWindow(BaseAppForm, Ui_MainWindow):
    def __init__(self, version, **kws):
        super(self.__class__, self).__init__()

        # app version, title
        self.setAppVersion(version)
        self.setAppTitle("My App")

        # app info in about dialog
        # self.app_about_info = "About info of My App."

        # UI
        self.setupUi(self)
        self.postInitUi()

        # post init
        self._post_init()

    def _post_init(self):
        """Initialize UI, user customized code put here.
        """
        # initial vars for FLAME model
        self.results = None
        self.last_bs = None
        self.fm = None

        # ElementWidget for selected quad and target element
        self._quad_widget = None
        self._elem_widget = None

        # Fill comboBox quad1_name_cbb with all quad names.
        quad_name_list = [i.name for i in ARIS_MP.get_elements(type='QUAD')]
        self.quad1_name_cbb.addItems(quad_name_list)
        # connect currentTextChanged signal to slot: on_quad1_name_changed()
        self.quad1_name_cbb.currentTextChanged.connect(
            self.on_quad1_name_changed)
        # connect valueChanged signal of quad1_grad_dsbox to on_quad1_grad_changed()
        self.quad1_grad_dsbox.valueChanged.connect(self.on_quad1_grad_changed)
        # initialize quad1_name_cbb
        self.quad1_name_cbb.currentTextChanged.emit(quad_name_list[0])

        # initial elemlist_cbb
        self.init_elemlist()

        # envelope curves
        o = self.envelope_plot
        o.add_curve()
        o.setLineID(0)  # X
        o.setLineColor(QColor('#0000FF'))
        o.setLineLabel("$\sigma_x$")
        o.setLineID(1)  # Y
        o.setLineColor(QColor('#FF0000'))
        o.setLineLabel("$\sigma_y$")

        # ellipse drawing figure configuration
        for o in (self.xlim_x1_lineEdit, self.xlim_x2_lineEdit, ):
            o.setValidator(QDoubleValidator())
            o.textChanged.connect(self.on_xlimit_changed)

        for o in (self.ylim_y1_lineEdit, self.ylim_y2_lineEdit, ):
            o.setValidator(QDoubleValidator())
            o.textChanged.connect(self.on_ylimit_changed)

        self.grid_on_chkbox.toggled.connect(self.on_grid_enabled)
        self.mticks_on_chkbox.toggled.connect(self.on_mticks_enabled)
        self.tight_layout_on_chkbox.toggled.connect(self.on_tightlayout_enabled)

        # update drawing
        self.quad1_grad_dsbox.valueChanged.emit(self.quad1_grad_dsbox.value())
        # reset current selected element with the last element
        self.elemlist_cbb.setCurrentIndex(self.elemlist_cbb.count() - 1)
        self.elemlist_cbb.currentTextChanged.emit(self.elemlist_cbb.currentText())

        # element query
        self.quad_info_btn.clicked.connect(self.on_query_quad_info)
        self.elem_info_btn.clicked.connect(self.on_query_elem_info)

    @pyqtSlot('QString')
    def on_quad1_name_changed(self, name: str) -> None:
        """When the current selected quad name is changed, do:
        show the current setting of the selected quad on quad1_grad_dsbox.
        when set value to quad1_grad_dsbox, disconnect valueChanged and
        reconnect, to avoid unnecessary trigging.
        """
        self.quad_selected = ARIS_MP.get_elements(name=name)[0]
        self._quad_widget = ElementWidget(self.quad_selected)
        self.quad1_grad_dsbox.valueChanged.disconnect()
        try:
            self.quad1_grad_dsbox.setValue(
                self.quad_selected.current_setting('B2'))
        except TypeError:
            # current_settings('B2') is None --> most likely VA is not running
            QMessageBox.critical(
                self, "ARIS Beam Ellipse",
                "Cannot reach process variables, please either start virtual accelerator or ensure Channel Access is permittable.",
                QMessageBox.Ok, QMessageBox.Ok)
            sys.exit(1)

        self.quad1_grad_dsbox.valueChanged.connect(self.on_quad1_grad_changed)

    @pyqtSlot(float)
    def on_quad1_grad_changed(self, grad: float) -> None:
        """When the setting of the selected quad is changed, do:
        1. print the setting of selected quad
        2. update drawing with online simulated results
        """
        self.quad_selected.B2 = grad
        # update simulation
        ARIS_LAT.sync_settings()
        _, fm = ARIS_LAT.run()
        self.fm = fm
        self.results, _ = fm.run(monitor='all')
        r, _ = fm.run(monitor=[self.elemlist_cbb.currentText()])
        if r != []:
            self.last_bs = r[0][-1]

        # update drawing
        self.update_drawing()

    def update_drawing(self):
        """This is the routine to update the figure with the updated drawing.
        Here I'm drawing the beam envelop along the entire beamline, try to
        replace with your routine for beam ellipse drawing.
        """
        self.draw_envelope()
        self.draw_ellipse()

    def draw_envelope(self):
        """Draw beam envelop onto the figure area.
        """
        results_dict = self.fm.collect_data(self.results, 'pos', 'xrms',
                                            'yrms')
        pos = results_dict['pos']
        xrms = results_dict['xrms']
        yrms = results_dict['yrms']
        # update drawing
        # Note: matplotlibbaseWidget is used here for generic drawing,
        # for curve visualization, matplotlibCurveWidget is a better choice.
        # x
        self.envelope_plot.setLineID(0)
        self.envelope_plot.update_curve(pos, xrms)
        # y
        self.envelope_plot.setLineID(1)
        self.envelope_plot.update_curve(pos, yrms)

    def draw_ellipse(self):
        """Draw x and y beam ellipse onto the figure area.
        """
        #
        s = self.last_bs
        #
        vals_x = (s.xcen, s.xpcen, s.xrms, s.xprms, s.xemittance,
                  s.xnemittance, s.xtwiss_alpha, s.xtwiss_beta,
                  (s.xtwiss_alpha**2 + 1) / s.xtwiss_beta, 1)
        vals_y = (s.ycen, s.ypcen, s.yrms, s.yprms, s.yemittance,
                  s.ynemittance, s.ytwiss_alpha, s.ytwiss_beta,
                  (s.ytwiss_alpha**2 + 1) / s.ytwiss_beta, 1)
        params_x = dict(zip(TWISS_KEYS_X, vals_x))
        params_y = dict(zip(TWISS_KEYS_Y, vals_y))

        self._plot_ellipse(self.x_ellipse_plot,
                           params_x,
                           color='b',
                           factor=4,
                           xoy='x',
                           fill='g',
                           anote=False)
        self._plot_ellipse(self.y_ellipse_plot,
                           params_y,
                           color='r',
                           factor=4,
                           xoy='y',
                           fill='m',
                           anote=False)
        #
        params = {k: v for k, v in params_x.items()}
        params.update(params_y)
        data = [(k, v, '-') for k, v in params.items()]
        self._show_results(data)


    def _plot_ellipse(self, figure_obj, params, **kws):
        xoy = kws.get('xoy', 'x')
        xlbl = f"{xoy} [mm]"
        ylbl = f"{xoy}' [mrad]"
        figure_obj.clear_figure()
        draw_beam_ellipse_with_params(params,
                                      ax=figure_obj.axes,
                                      color=kws.get('color', 'b'),
                                      factor=kws.get('factor', 4),
                                      xoy=xoy,
                                      fill=kws.get('fill', 'g'),
                                      anote=kws.get('anote', False))
        figure_obj.setFigureXlabel(xlbl)
        figure_obj.setFigureYlabel(ylbl)
        figure_obj.update_figure()
        self.on_xlimit_changed('')
        self.on_ylimit_changed('')
        self.grid_on_chkbox.toggled.emit(self.grid_on_chkbox.isChecked())
        self.mticks_on_chkbox.toggled.emit(self.mticks_on_chkbox.isChecked())
        self.tight_layout_on_chkbox.toggled.emit(self.tight_layout_on_chkbox.isChecked())

    def init_elemlist(self):
        #
        # this should be called after machine/segment is changed
        # now only work with ARIS/F1, todo in the future with LatticeWidget
        #
        ename_list = [i.name for i in ARIS_LAT]
        self.elemlist_cbb.addItems(ename_list)
        self.elemlist_cbb.currentTextChanged.connect(self.on_target_element_changed)

    @pyqtSlot('QString')
    def on_target_element_changed(self, ename: str):
        """Get beam state result after the selected element from FLAME model.
        """
        elem = ARIS_LAT[ename]
        self._elem_widget = ElementWidget(elem)
        self.family_lineEdit.setText(elem.family)
        self.pos_lineEdit.setText(f"{elem.sb:.3f} m")
        r, _ = self.fm.run(monitor=[ename])
        if r == []:
            QMessageBox.warning(self, "Select Element",
                    "Selected element cannot be located in model, probably for splitable element, select the closest one.",
                    QMessageBox.Ok, QMessageBox.Ok)
            return
        self.last_bs = r[0][-1]
        self.draw_ellipse()

    def _show_results(self, data):
        from .utils import ResultsModel
        m = ResultsModel(self.twiss_results_treeView, data)
        m.set_model()

    @pyqtSlot()
    def on_query_quad_info(self):
        """Pop up dialog for selected quad for info query.
        """
        if self._quad_widget is None:
            return
        self._quad_widget.show()
        self._quad_widget.raise_()

    @pyqtSlot()
    def on_query_elem_info(self):
        """Pop up dialog for selected element for info query.
        """
        if self._elem_widget is None:
            return
        self._elem_widget.show()
        self._elem_widget.raise_()

    @pyqtSlot('QString')
    def on_xlimit_changed(self, s):
        """xlimit to be updated.
        """
        try:
            x1 = float(self.xlim_x1_lineEdit.text())
            x2 = float(self.xlim_x2_lineEdit.text())
        except ValueError:
            pass
        else:
            for o in self.ellipse_area.findChildren(MatplotlibBaseWidget):
                o.set_xlimit(x1, x2)

    @pyqtSlot('QString')
    def on_ylimit_changed(self, s):
        """ylimit to be updated.
        """
        try:
            y1 = float(self.ylim_y1_lineEdit.text())
            y2 = float(self.ylim_y2_lineEdit.text())
        except ValueError:
            pass
        else:
            for o in self.ellipse_area.findChildren(MatplotlibBaseWidget):
                o.set_ylimit(y1, y2)

    @pyqtSlot(bool)
    def on_grid_enabled(self, enabled):
        for o in self.ellipse_area.findChildren(MatplotlibBaseWidget):
            o.setFigureGridToggle(enabled)

    @pyqtSlot(bool)
    def on_mticks_enabled(self, enabled):
        for o in self.ellipse_area.findChildren(MatplotlibBaseWidget):
            o.setFigureMTicksToggle(enabled)

    @pyqtSlot(bool)
    def on_tightlayout_enabled(self, enabled):
        for o in self.ellipse_area.findChildren(MatplotlibBaseWidget):
            o.setTightLayoutToggle(enabled)


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    version = 0.1
    app = QApplication(sys.argv)
    w = MyAppWindow(version)
    w.show()
    w.setWindowTitle("This is an app from template")
    sys.exit(app.exec_())
