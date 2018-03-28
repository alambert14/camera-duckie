#!/usr/bin/env python
import rospy
import math
from duckietown_msgs.msg import Twist2DStamped, LanePose, BoolStamped, FSMState
from controller import Controller # import the PI controller
import time

class lane_controller(object):
    def __init__(self):
        self.node_name = rospy.get_name()
        self.lane_reading = None

        self.pub_counter = 0

        # Setup parameters
        self.setGains()

        # Publicaiton
        self.pub_car_cmd = rospy.Publisher("~car_cmd", Twist2DStamped, queue_size=1)

        # Subscriptions
        self.sub_lane_reading = rospy.Subscriber("~lane_pose", LanePose, self.cbPose, queue_size=1)
        self.sub_fsm_mode = rospy.Subscriber("~fsm_mode", FSMState, self.cbMode, queue_size=1)
        # safe shutdown
        rospy.on_shutdown(self.custom_shutdown)

        # timer
        self.gains_timer = rospy.Timer(rospy.Duration.from_sec(1.0), self.getGains_event)
        rospy.loginfo("[%s] Initialized " %(rospy.get_name()))

        # initialize Controller: k_P, k_I, u_sat, k_t, C(1), C(2)
        # where C = [C(1) C(2)] is the C matrix of the LTI system
        # which is something like [6 1] for the states x = [d phi]
        self.controller = Controller(4, 1, 4, 1, 6, 1)

        self.last_ms = None
        self.operating = False

    def setupParameter(self,param_name,default_value):
        value = rospy.get_param(param_name,default_value)
        rospy.set_param(param_name,value) #Write to parameter server for transparancy
        rospy.loginfo("[%s] %s = %s " %(self.node_name,param_name,value))
        return value

    def setGains(self):
        v_bar = 0.22
        k_P = 4
        k_I = 1
        u_sat = 5
        k_t = 1
        c1 = 6
        c2 = 1

        self.v_bar = self.setupParameter("~v_bar",v_bar) # Linear velocity
        self.k_P = self.setupParameter("~k_P",k_P)
        self.k_I = self.setupParameter("~k_I",k_I)
        self.u_sat = self.setupParameter("~u_sat",u_sat)
        self.k_t = self.setupParameter("~k_t",k_t)
        self.c1 = self.setupParameter("~c1",c1)
        self.c2 = self.setupParameter("~c2",c2)

    def getGains_event(self, event):
        v_bar = rospy.get_param("~v_bar") # Linear velocity
        k_P = rospy.get_param("~k_P")
        k_I = rospy.get_param("~k_I")
        u_sat = rospy.get_param("~u_sat")
        k_t = rospy.get_param("~k_t")
        c1 = rospy.get_param("~c1")
        c2 = rospy.get_param("~c2")

        params_old = (self.v_bar, self.k_P, self.k_I, self.u_sat, self.k_t, self.c1, self.c2)
        params_new = (v_bar, k_P, k_I, u_sat, k_t, c1, c2)

        if params_old != params_new:
            rospy.loginfo("[%s] Gains changed." %(self.node_name))
            self.controller.updateParams(k_P, k_I, u_sat, k_t, c1, c2)
            self.v_bar = v_bar
            self.k_P = k_P
            self.k_I = k_I
            self.u_sat = u_sat
            self.k_t = k_t
            self.c1 = c1
            self.c2 = c2


    def custom_shutdown(self):
        rospy.loginfo("[%s] Shutting down..." %self.node_name)

        # Stop listening
        self.sub_lane_reading.unregister()

        # Send stop command
        car_control_msg = Twist2DStamped()
        car_control_msg.v = 0.0
        car_control_msg.omega = 0.0
        self.publishCmd(car_control_msg)
        rospy.sleep(0.5) #To make sure that it gets published.
        rospy.loginfo("[%s] Shutdown" %self.node_name)

    # FSM
    def cbMode(self,fsm_state_msg):
        self.operating = fsm_state_msg.state == "LANE_FOLLOWING"

    def publishCmd(self, car_cmd_msg):
        self.pub_car_cmd.publish(car_cmd_msg)

    def cbPose(self, lane_pose_msg):

        self.lane_reading = lane_pose_msg
        self.v_bar = 0.22 #TODO hardcoded

        # Calculating the delay image processing took
        timestamp_now = rospy.Time.now()
        image_delay_stamp = timestamp_now - self.lane_reading.header.stamp

        # delay from taking the image until now in seconds
        image_delay = image_delay_stamp.secs + image_delay_stamp.nsecs/1e9

        # Calculate time since last command
        currentMillis = int(round(time.time() * 1000))
        if self.last_ms is not None:
            dt_last = (currentMillis - self.last_ms) / 1000.0
        else:
            dt_last = 0

        # Return if not in autopilot
        if not self.operating:
            self.last_ms = currentMillis
            return

        v_ref = self.v_bar
        d_ref = 0
        phi_ref = 0
        d_est = lane_pose_msg.d
        phi_est = lane_pose_msg.phi


        v_out, omega_out = self.controller.getControlOutput(d_est, phi_est,
                            d_ref, phi_ref, v_ref, image_delay, dt_last) #TODO dt_last


        car_control_msg = Twist2DStamped()
        car_control_msg.header = lane_pose_msg.header
        car_control_msg.v = v_out

        car_control_msg.omega = omega_out


        self.publishCmd(car_control_msg)

        self.last_ms = currentMillis


if __name__ == "__main__":
    rospy.init_node("lane_controller",anonymous=False)
    lane_control_node = lane_controller()
    rospy.spin()
