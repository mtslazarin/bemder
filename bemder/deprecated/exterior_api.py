#%%

import bempp.api
import numpy as np


from matplotlib import pylab as plt

bempp.api.PLOT_BACKEND = "gmsh"


bempp.api.show_available_platforms_and_devices()
bempp.api.set_default_device(0,1)
print('\nSelected device:', bempp.api.default_device().name) 
#bempp.api.GLOBAL_PARAMETERS.assembly.dense
    

  
#%%
class ExteriorBEM:
    
    """
    Hi, this class contains some tools to solve the interior acoustic problem with monopole point sources. First, you gotta 
    give some inputs:
        
    Inputs:
        
        space = bempp.api.function_space(grid, "DP", 0) || grid = bempp.api.import_grid('#YOURMESH.msh')
        
        f_range = array with frequencies of analysis. eg:   f1= 20
                                                            f2 = 150
                                                            df = 2
                                                            f_range = np.arange(f1,f2+df,df) 
        
        c0 = speed of sound
        
        r0 = dict[0:numSources] with source positions. eg:  r0 = {}
                                                            r0[0] =  np.array([1.4,0.7,-0.35])
                                                            r0[1] = np.array([1.4,-0.7,-0.35])
                                                            
        q = dict[0:numSources] with constant source strenght S. eg: q = {}
                                                                    q[0] = 1
                                                                    q[1] = 1
        
        mu = dict[physical_group_id]| A dictionary containing f_range sized arrays with admittance values. 
        The key (index) to the dictionary must be the physical group ID defined in Gmsh. If needed, check out
        the bemder.porous functions :). 
                                        eg: zsd1 = porous.delany(5000,0.1,f_range)
                                            zsd2 = porous.delany(10000,0.2,f_range)
                                            zsd3 = porous.delany(15000,0.3,f_range)
                                            mud1 = np.complex128(rho0*c0/np.conj(zsd1))
                                            mud2 = np.complex128(rho0*c0/np.conj(zsd2))
                                            mud3 = np.complex128(rho0*c0/np.conj(zsd3))
                                            
                                            mu = {}
                                            mu[1] = mud2
                                            mu[2] = mud2
                                            mu[3] = mud3
        
        

    """
    #then = time.time()
    def __init__(self,space,f_range,r0,q,mu,v=0,c0=343,rho0=1.21):
        self.space = space
        self.f_range = f_range
        self.r0 = r0
        self.q = q
        self.mu = mu
        self.v = v
        self.c0 = c0
        self.rho0 = rho0
    def velocity_bemsolve(self):
        """
        Computes the bempp gridFunctions for the interior acoustic problem.
        
        Outputs: 
            
            boundP = grid_function for boundary pressure
            
            boundU = grid_function for boundary velocity
        
        """
        
        p = {}
        u ={}
        
        for fi in range(np.size(self.f_range)):
        
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0 # Calculate wave number
            @bempp.api.real_callable(jit=False) 
            def mu_fun_r(r,n,domain_index,result):
                result[0]=np.real(self.mu[domain_index][fi])
            @bempp.api.real_callable(jit=False) 
            def mu_fun_i(r,n,domain_index,result):
                result[0]=np.imag(self.mu[domain_index][fi])
                
            @bempp.api.real_callable(jit=False) 
            def v_data(r,n,domain_index,result):
                result[0] = self.v[domain_index][fi] * (n[0]-1)
            
            
                
            
            mu_op_r = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_r),self.space,self.space,self.space)
            mu_op_i = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_i),self.space,self.space,self.space)
        
            identity = bempp.api.operators.boundary.sparse.identity(
                self.space, self.space, self.space)
            dlp = bempp.api.operators.boundary.helmholtz.adjoint_double_layer(
                self.space, self.space, self.space, k)
            slp = bempp.api.operators.boundary.helmholtz.single_layer(
                self.space, self.space, self.space, k)
        
            @bempp.api.complex_callable(jit=False)
            def monopole_data(r, n, domain_index, result):
                result[0]=0
                for i in range(len(self.q)):
                    pos = np.linalg.norm(r-self.r0[i])
                    val  = self.q[i]*np.exp(1j*k*pos)/(4*np.pi*pos)
                    result[0] +=  -(1j*self.mu[domain_index][fi]*k*val - val/(pos*pos) * (1j*k*pos-1)* np.dot(r-self.r0[i],n))

   
            v_fun = bempp.api.GridFunction(self.space, fun=v_data)
            monopole_fun = bempp.api.GridFunction(self.space, fun=monopole_data)
        
        
            lhs = (.5 * identity - dlp + 1j*k*slp*(mu_op_r+1j*mu_op_i)) 
            rhs = slp*(monopole_fun + 1j*k*self.rho0*self.c0*v_fun)
        
        
        
            boundP, info = bempp.api.linalg.iterative_solvers.gmres(lhs, rhs, tol=1E-5, use_strong_form=True)
        
            boundU = 1j*(mu_op_r+1j*mu_op_i)*k*boundP - monopole_fun + 1j*self.c0*self.rho0*k*v_fun
            
            p[fi] = boundP
            u[fi] = boundU
            
            
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
        return p,u
       
    def combined_bemsolve(self):
        """
        Computes the bempp gridFunctions for the interior acoustic problem.
        
        Outputs: 
            
            boundP = grid_function for boundary pressure
            
            boundU = grid_function for boundary velocity
        
        """
        
        p = {}
        
        for fi in range(np.size(self.f_range)):
        
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0 # Calculate wave number


            

            identity = bempp.api.operators.boundary.sparse.identity(
                self.space, self.space, self.space)
            dlp = bempp.api.operators.boundary.helmholtz.adjoint_double_layer(
                self.space, self.space, self.space, k)
            slp = bempp.api.operators.boundary.helmholtz.single_layer(
                self.space, self.space, self.space, k)
        
            @bempp.api.complex_callable(jit=False)
            def v_data(r, n, domain_index, result):
                result[0] =self.v[domain_index][fi]
   
            v_fun = bempp.api.GridFunction(self.space, fun=v_data)
            
        
            lhs = (.5 * identity + dlp - 1j*k*slp) 
            rhs = slp*(v_fun)
        
        
        
            boundP, info = bempp.api.linalg.iterative_solvers.gmres(lhs, rhs, tol=1E-5)

            
            p[fi] = boundP
            
            
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
        return p
       
  
    def bemsolve(self):
        """
        Computes the bempp gridFunctions for the interior acoustic problem.
        
        Outputs: 
            
            boundP = grid_function for boundary pressure
            
            boundU = grid_function for boundary velocity
        
        """
        
        p = {}
        u ={}
        
        for fi in range(np.size(self.f_range)):
        
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0 # Calculate wave number
            @bempp.api.real_callable(jit=False) 
            def mu_fun_r(r,n,domain_index,result):
                result[0]=np.real(self.mu[domain_index][fi])
            @bempp.api.real_callable(jit=False) 
            def mu_fun_i(r,n,domain_index,result):
                result[0]=np.imag(self.mu[domain_index][fi])
            
            mu_op_r = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_r),self.space,self.space,self.space)
            mu_op_i = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_i),self.space,self.space,self.space)
        
            identity = bempp.api.operators.boundary.sparse.identity(
                self.space, self.space, self.space)
            dlp = bempp.api.operators.boundary.helmholtz.adjoint_double_layer(
                self.space, self.space, self.space, k)
            slp = bempp.api.operators.boundary.helmholtz.single_layer(
                self.space, self.space, self.space, k)
            
        
            @bempp.api.complex_callable(jit=False)
            def monopole_data(r, n, domain_index, result):
                result[0]=0
                for i in range(len(self.q)):
                    pos = np.linalg.norm(r-self.r0[i])
                    val  = self.q[i]*(np.exp(1j*k*pos)/(4*np.pi*pos))
                    result[0] +=  -(1j*self.mu[domain_index][fi]*k*val - 1j*val/(pos*pos*self.rho0*self.c0*k) * (1j*k*pos-1)* np.dot(r-self.r0[i],n))
            
                
            monopole_fun = bempp.api.GridFunction(self.space, fun=monopole_data)
        
        
            lhs = (.5 * identity + dlp - 1j*k*slp*(mu_op_r+1j*mu_op_i)) -1j*k*slp
            rhs = slp*monopole_fun

        
        
            boundP, info = bempp.api.linalg.iterative_solvers.gmres(lhs, rhs, tol=1E-5)
        
            boundU = 1j*(mu_op_r+1j*mu_op_i)*k*boundP - monopole_fun
            
            p[fi] = boundP
            u[fi] = boundU
            
            
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
        return p,u
    
    def ousado_bemsolve(self):
        """
        Computes the bempp gridFunctions for the interior acoustic problem.
        
        Outputs: 
            
            boundP = grid_function for boundary pressure
            
            boundU = grid_function for boundary velocity
        
        """
        
        p = {}
        u ={}
        
        for fi in range(np.size(self.f_range)):
        
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0 # Calculate wave number
            @bempp.api.real_callable(jit=False) 
            def mu_fun_r(r,n,domain_index,result):
                result[0]=np.real(self.mu[domain_index][fi])
            @bempp.api.real_callable(jit=False) 
            def mu_fun_i(r,n,domain_index,result):
                result[0]=np.imag(self.mu[domain_index][fi])
            
            mu_op_r = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_r),self.space,self.space,self.space)
            mu_op_i = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_i),self.space,self.space,self.space)
        
            identity = bempp.api.operators.boundary.sparse.identity(
                self.space, self.space, self.space)
            dlp = bempp.api.operators.boundary.helmholtz.double_layer(
                self.space, self.space, self.space, k)
            adlp = bempp.api.operators.boundary.helmholtz.adjoint_double_layer(
                self.space, self.space, self.space, k)
            slp = bempp.api.operators.boundary.helmholtz.single_layer(
                self.space, self.space, self.space, k)
            hyp = bempp.api.operators.boundary.helmholtz.hypersingular(
                self.space, self.space, self.space, k)
            
            @bempp.api.complex_callable(jit=False)
            def monopole_data(r, n, domain_index, result):
                result[0]=0
                for i in range(len(self.q)):
                    pos = np.linalg.norm(r-self.r0[i])
                    val  = self.q[i]*np.exp(1j*k*pos)/(4*np.pi*pos)
                    result[0] +=  -(1j*self.mu[domain_index][fi]*k*val - val/(pos*pos) * (1j*k*pos-1)* np.dot(r-self.r0[i],n-1))
                       
                
            monopole_fun = bempp.api.GridFunction(self.space, fun=monopole_data)


        
            A = 0.5*identity + adlp - 1j*k*slp*(mu_op_r+1j*mu_op_i)
            B = hyp + 1j*k*(0.5*identity - dlp)*(mu_op_r+1j*mu_op_i)
            C = -hyp + k**2*(mu_op_r+1j*mu_op_i)*slp*(mu_op_r+1j*mu_op_i) - 1j*k*(mu_op_r+1j*mu_op_i)*adlp -1j*k*(mu_op_r+1j*mu_op_i)*dlp

            
            Ar = -slp*monopole_fun
            Br = (0.5*identity + adlp)*monopole_fun
#            
            lhs = C
            rhs = monopole_fun

        
        
            boundP, info = bempp.api.linalg.iterative_solvers.gmres(lhs, rhs, tol=1E-5)
        
            boundU = 1j*(mu_op_r+1j*mu_op_i)*k*boundP + monopole_fun
            
            p[fi] = boundP
            u[fi] = boundU
            
            
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
        return p,u
    def ORSC_bemsolve(self):
        """
        Computes the bempp gridFunctions for the interior acoustic problem.
        
        Outputs: 
            
            boundP = grid_function for boundary pressure
            
            boundU = grid_function for boundary velocity
        
        """
        
        p = {}
        u ={}
        
        for fi in range(np.size(self.f_range)):
        
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0 # Calculate wave number
            @bempp.api.real_callable(jit=False) 
            def mu_fun_r(r,n,domain_index,result):
                result[0]=np.real(self.mu[domain_index][fi])
            @bempp.api.real_callable(jit=False) 
            def mu_fun_i(r,n,domain_index,result):
                result[0]=np.imag(self.mu[domain_index][fi])
            
            mu_op_r = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_r),self.space,self.space,self.space)
            mu_op_i = bempp.api.MultiplicationOperator(bempp.api.GridFunction(self.space,fun=mu_fun_i),self.space,self.space,self.space)
        
            identity = bempp.api.operators.boundary.sparse.identity(
                self.space, self.space, self.space)
            dlp = bempp.api.operators.boundary.helmholtz.double_layer(
                self.space, self.space, self.space, k)
            slp = bempp.api.operators.boundary.helmholtz.single_layer(
                self.space, self.space, self.space, k)
            hyp = bempp.api.operators.boundary.helmholtz.hypersingular(
                    self.space, self.space, self.space, k)            
        
            @bempp.api.complex_callable(jit=False)
            def monopole_data(r, n, domain_index, result):
                result[0]=0
                for i in range(len(self.q)):
                    pos = np.linalg.norm(r-self.r0[i])
                    val  = self.q[i]*np.exp(1j*k*pos)/(4*np.pi*pos)
                    result[0] +=  -(1j*self.mu[domain_index][fi]*k*val - val/(pos*pos) * (1j*k*pos-1)* np.dot(r-self.r0[i],n))
            
                
            monopole_fun = bempp.api.GridFunction(self.space, fun=monopole_data)
        
        
            lhs = (1j*k*(.5 * identity + dlp) - hyp + (mu_op_r+1j*mu_op_i)*(1j*k*slp+(-0.5*identity+dlp)))
            rhs = monopole_fun
        
        
        
            boundP, info = bempp.api.linalg.iterative_solvers.gmres(lhs, rhs, tol=1E-5, use_strong_form=True)
        
            boundU = 1j*(mu_op_r+1j*mu_op_i)*k*boundP + monopole_fun
            
            p[fi] = boundP
            u[fi] = boundU
            
            
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
        return p,u
    def monopole(self,fi,pts):
        
        pInc = np.zeros(pts.shape[0], dtype='complex128')
        
        for i in range(len(self.q)): 
            pos = np.linalg.norm(pts-self.r0[i].reshape(1,3),axis=1)
            pInc += self.q[i]*np.exp(1j*(2*np.pi*self.f_range[fi]/self.c0)*pos)/(4*np.pi*pos)
            
        return pInc  
    
    def point_evaluate(self,points, boundP,boundU):
        
        """
        Evaluates the solution (pressure) for a point.
        
        Inputs:
            points = dict[0:numPoints] containing np arrays with receiver positions 
            
            boundP = output from bemsolve()
            
            boundU = output from bemsolve()
            
        Output:
            
           pT =  Total Pressure Field
           
        """
        pT = {}
        pts = np.array([points[i] for i in points.keys()]).reshape(len(points),3)

        for fi in range(np.size(self.f_range)):
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0
                
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, pts.T, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, pts.T, k)
            pScat =  (-dlp_pot * boundP[fi] + slp_pot * boundU[fi])
            
            pInc = self.monopole(fi,pts)
            
            pT[fi] = (pInc+pScat)

            print(20*np.log10(np.abs(pT[fi])/2e-5))
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
            
        return  np.array([pT[i] for i in pT.keys()]).reshape(len(pT),len(points))

    def ORSC_point_evaluate(self,points, boundP,boundU):
        
        """
        Evaluates the solution (pressure) for a point.
        
        Inputs:
            points = dict[0:numPoints] containing np arrays with receiver positions 
            
            boundP = output from bemsolve()
            
            boundU = output from bemsolve()
            
        Output:
            
           pT =  Total Pressure Field
           
        """
        pT = {}
        pts = np.array([points[i] for i in points.keys()]).reshape(len(points),3)

        for fi in range(np.size(self.f_range)):
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0
                
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, pts.T, k)
#            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
#                self.space, pts.T, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(self.space, pts.T, k)
            pScat =   dlp_pot * boundP[fi] + 1j*k*slp_pot*boundP[fi]
            
            pInc = self.monopole(fi,pts)
            
            pT[fi] = (pInc+pScat)

            print(20*np.log10(np.abs(pT[fi])/2e-5))
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
            
        return  np.array([pT[i] for i in pT.keys()]).reshape(len(pT),len(points))

    def combined_point_evaluate(self,points, boundP):
        
        """
        Evaluates the solution (pressure) for a point.
        
        Inputs:
            points = dict[0:numPoints] containing np arrays with receiver positions 
            
            boundP = output from bemsolve()
            
            boundU = output from bemsolve()
            
        Output:
            
           pT =  Total Pressure Field
           
        """
        pT = {}
        pts = np.array([points[i] for i in points.keys()]).reshape(len(points),3)

        for fi in range(np.size(self.f_range)):
            f = self.f_range[fi] #Convert index to frequency
            k = 2*np.pi*f/self.c0
                
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, pts.T, k)

            pScat =  -slp_pot * boundP[fi]
 
            pT[fi] = np.conj(pScat)

            print(20*np.log10(np.abs(pT[fi])/2e-5))
            print('{} / {}'.format(fi+1,np.size(self.f_range)))
            
        return  np.array([pT[i] for i in pT.keys()]).reshape(len(pT),len(points))    
    def grid_evaluate(self,fi,plane,d,grid_size,n_grid_pts,boundP,boundU,savename=None):
        
        """
        Evaluates and plots the SPL in symmetrical grid for a mesh centered at [0,0,0].
        
        Inputs:
            
            fi = frequency index of array f_range
            
            plane = string containg axis to plot. eg: 'xy'
            
            d = Posistion of free axis (in relation to center)
            
            grid_size = Size of dimension to plot
            
            n_grid_pts = number of grid points
            
            boundP = output from bemsolve()
            
            boundU = output from bemsolve()
        """
        pT = {}
        
        k = 2*np.pi*self.f_range[fi]/self.c0
        
        if plane == 'xy':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[0]/2:grid_size[0]/2:n_grid_points*1j, -grid_size[1]/2:grid_size[1]/2:n_grid_points*1j]
            grid_pts = np.vstack((plot_grid[0].ravel(),plot_grid[1].ravel(),d+np.zeros(plot_grid[0].size)))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pScat+pInc)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),  cmap='jet')
            plt.colorbar()
            plt.show()
            
            return grid_pT

        if plane == 'xy_c':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[grid_size[0]:0:n_grid_points*1j, grid_size[1]:0:n_grid_points*1j]
            grid_pts = np.vstack((plot_grid[0].ravel(),plot_grid[1].ravel(),d+np.zeros(plot_grid[0].size)))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pScat+pInc)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            if savename == None:
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),  cmap='jet')
                plt.colorbar()
                plt.show()
            else:
                fig = plt.figure(frameon=False)
                ax = plt.Axes(fig, [0., 0., 1., 1.])
                ax.set_axis_off()
                fig.add_axes(ax)
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),cmap='jet')
                plt.savefig('plane.png',dpi=500)
                plt.show()
            return grid_pT
        
        if plane == 'yx':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[1]/2:grid_size[1]/2:n_grid_points*1j, -grid_size[0]/2:grid_size[0]/2:n_grid_points*1j]
            grid_pts = np.vstack((plot_grid[1].ravel(),plot_grid[0].ravel(),d+np.zeros(plot_grid[0].size)))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pInc+pScat)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[1],0,grid_size[0]),  cmap='jet')
            plt.colorbar()
            plt.show()
            
            return grid_pT
        if plane == 'xz_c':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[0]/2:grid_size[0]/2:n_grid_points*1j, grid_size[1]:0:n_grid_points*1j]
            grid_pts = np.vstack((plot_grid[0].ravel(),d+np.zeros(plot_grid[0].size),plot_grid[1].ravel()))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pScat+pInc)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            if savename == None:
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(-grid_size[0]/2,grid_size[0]/2,0,grid_size[1]),  cmap='jet')
                plt.colorbar()
                plt.show()
            else:
                fig = plt.figure(frameon=False)
                ax = plt.Axes(fig, [0., 0., 1., 1.])
                ax.set_axis_off()
                fig.add_axes(ax)
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5),cmap='jet')
                plt.savefig('plane.png',dpi=500)
                plt.show()
            return grid_pT
        if plane == 'xz':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[0]/2:grid_size[0]/2:n_grid_points*1j, -grid_size[1]/2:grid_size[1]/2:n_grid_points*1j]
            grid_pts = np.vstack((plot_grid[0].ravel(),d+np.zeros(plot_grid[0].size),plot_grid[1].ravel()))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pInc+pScat)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            if savename == None:
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),  cmap='jet')
                plt.colorbar()
                plt.show()
            else:
                fig = plt.figure(frameon=False)
                ax = plt.Axes(fig, [0., 0., 1., 1.])
                ax.set_axis_off()
                fig.add_axes(ax)
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),cmap='jet')
                plt.savefig('%s.png'%ax,dpi=500)
                plt.show()
            return grid_pT
        if plane == 'zx':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[1]/2:grid_size[1]/2:n_grid_points*1j, -grid_size[0]/2:grid_size[0]/2:n_grid_points*1j]
            grid_pts = np.vstack((plot_grid[1].ravel(),d+np.zeros(plot_grid[1].size),plot_grid[0].ravel()))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pInc+pScat)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            if savename == None:
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),  cmap='jet')
                plt.colorbar()
                plt.show()
            else:
                fig = plt.figure(frameon=False)
                ax = plt.Axes(fig, [0., 0., 1., 1.])
                ax.set_axis_off()
                fig.add_axes(ax)
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),cmap='jet')
                plt.savefig('%s.png'%savename,dpi=500)
                plt.show()
            return grid_pT
        if plane == 'yz':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[0]/2:grid_size[0]/2:n_grid_points*1j, -grid_size[1]/2:grid_size[1]/2:n_grid_points*1j]
            grid_pts = np.vstack((d+np.zeros(plot_grid[0].size),plot_grid[0].ravel(),plot_grid[1].ravel()))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pInc+pScat)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            if savename == None:
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),  cmap='jet')
                plt.colorbar()
                plt.show()
            else:
                fig = plt.figure(frameon=False)
                ax = plt.Axes(fig, [0., 0., 1., 1.])
                ax.set_axis_off()
                fig.add_axes(ax)
                plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),cmap='jet')
                plt.savefig('%s.png'%ax,dpi=500)
                plt.show()
            
            return grid_pT
        if plane == 'zx':
            n_grid_points = n_grid_pts
            plot_grid = np.mgrid[-grid_size[1]/2:grid_size[1]/2:n_grid_points*1j, -grid_size[0]/2:grid_size[0]/2:n_grid_points*1j]
            grid_pts = np.vstack((d+np.zeros(plot_grid[1].size),plot_grid[1].ravel(),plot_grid[0].ravel()))
                          
            
            
            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
                self.space, grid_pts, k)
            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
                self.space, grid_pts, k)
            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
            
            pInc = self.monopole(fi,grid_pts.T)
            
            grid_pT = np.conj(pInc+pScat)
            
            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
            
            plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[1],0,grid_size[0]),  cmap='jet')
            plt.colorbar()
            plt.show()
            
            return grid_pT

#    def custom_grid_evaluate(self,fi,plane,d,gsize,n_grid_pts,boundP,boundU):
#        
#        """
#        
#        """
#        pT = {}
#        
#        k = 2*np.pi*self.f_range[fi]/self.c0
#        
#        if plane == 'xy':
#            grid_size[0] = gsize[0]; grid_size[1] = gsize[1]; grid_size[2] = gsize[2]; grid_size[3] = gsize[3];
#            grid_size[4] = -gsize[0]/2; grid_size[5] = gsize[5]/2
#    
#            
#            np.zeros(plot_grid[0].size)
#        
#            n_grid_points = n_grid_pts
#            plot_grid = np.mgrid[grid_size[0]:grid_size[1]:n_grid_points*1j, grid_size[2]:grid_size[3]:n_grid_points*1j,grid_size[4]:grid_size[4]:n_grid_points*1j]
#            grid_pts = np.vstack((plot_grid[0].ravel(),plot_grid[1].ravel(),plot_grid[2].ravel()))
#                          
#            
#            
#            slp_pot = bempp.api.operators.potential.helmholtz.single_layer(
#                self.space, grid_pts, k)
#            dlp_pot = bempp.api.operators.potential.helmholtz.double_layer(
#                self.space, grid_pts, k)
#            pScat =  (slp_pot * boundU[fi] + dlp_pot * boundP[fi])
#            
#            pInc = self.monopole(fi,grid_pts.T)
#            
#            grid_pT = np.conj(pScat+pInc)
#            
#            pT[fi] = grid_pT.reshape((n_grid_points,n_grid_points))
#            
#            plt.imshow(20*np.log10(np.abs(pT[fi].T)/2e-5), extent=(0,grid_size[0],0,grid_size[1]),  cmap='jet')
#            plt.colorbar()
#            plt.show()
#            
#            return grid_pT