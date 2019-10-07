#  class imports
from .classes.tree import Tree
from .classes.sampler import Sampler
from .classes.plotter import Plotter
from .classes.traceback_info import TraceBackInfo
from .classes.strategy import Strategy
from .classes.node import Node
from .classes.leaf_node import LeafNode
from .classes.anytime import Anytime
# utilities imports
import multiprocessing
import datetime
import os
import hashlib
import numpy as np


class SpeculativeMonitor(object):
    """
    Clase principal, ejecuta el algoritmo de ejecucion especulativa
    y la entrega de datos anytime.
    policy: max_sim o descent_spec
    """
    def __init__(self, cpu_count=None, policy="max_sim"):
        self.anytime = False
        self.__count = None
        self.__msg = None
        self.__speculativeNode = None
        self.tree = Tree()
        self.pifile = None
        self.experimental_design = None
        self.instances = None
        self.global_results = None
        self.__totalSimulations = 10000
        self.iteration = 1
        # self.__numOfExecutions = 0
        self.s2id = {}
        self.s_id = 0
        self.the_end = False
        # self.algoritmos = dict()
        self.node_dict = dict()
        self.leaf_dict = dict()
        self.quality_animation = None
        self.parameter_histogram = None
        self.quality_frame = None
        self.sampler = Sampler()
        self.instances = None
        self.cpu_count = None
        self.optimisticQuality = dict()
        self.pessimisticQuality = dict()
        self.amplitude = dict()
        self.experiment_id = None
        self.tree_descent_outcome = None
        self.policy = policy
        self.tree_desc_likelihood = 0
        self.max_sim_likelihood = 0
        self._tree_descent_strategies = {}
        if cpu_count is None:
            self.cpu_count = multiprocessing.cpu_count()

    def bestStrategy(self, S1, S2):  # __range, delta_sig
        """
        Retorna la mejor estrategia entre dos,
        mediante el mensage especulativo.
        """
        print("##############################")
        print("bestStrategy")
        print("count:", self.__count)
        print("msg:", self.__msg)
        if self.__count < len(self.__msg):
            print("leyendo mensaje")
            print("self.__msg[self.__count] == 0 ?:", self.__msg[self.__count] == 0)
            if self.__msg[self.__count] == 0:
                print("especulativamente, gana izq")
                self.__count = self.__count+1
                return S1
            else:
                print("especulativamente, gana derecha")
                self.__count = self.__count+1
                return S2
        print("getting traceback info:")
        experiment_state = TraceBackInfo.getExperimentState()
        print("hash string experiment_state", experiment_state)
        print("node_dict:", self.node_dict)
        if experiment_state in self.node_dict:
            print("esta dentro del diccionario")
            self.__speculativeNode = self.node_dict[experiment_state]
        else:
            print("no esta en el diccionario")
            self.__speculativeNode = Node(S1, S2, len(self.instances), 0)
            print("__speculativeNode:", self.__speculativeNode)
            self.node_dict[experiment_state] = self.__speculativeNode

        print("self.node_dict: ")
        print(self.node_dict)
        print("##############################")
        raise ValueError
    """ funciones para agregar mas adelante"""
    # def best_param_value(self):
    #     pass

    # def bestParam(S0, param, values, pi, delta):
    #     SList = []
    #     for p in values:
    #         #  ---------------- crea copia de la estrategia
    #         S = Strategy(original=S0, new_params={param: p})
    #         #  -----------------S.params[param]=p
    #         S.name = 'Algo-'+param+"="+str(p)
    #         SList.append(S)

    #     Sbest = S0
    #     for S in SList:
    #         Sbest = bestStrategy(Sbest, S, pi, delta)
    #         if Sbest is not S0 : delta = 0.0
    #     return Sbest

    def speculative_execution(self, experimental_design, instances):
        self.initialize(experimental_design, instances)
        print("##############################")
        print("start_speculative_execution")
        while True:
            print("loop begin")
            self._tree_descent()
            max_leaf = self._update_likelihood()
            best_alg = self._select_strategy(max_leaf)
            if best_alg is not None:
                self._execute(best_alg)
                self._save_results(best_alg)
            else:
                break
            print("loop end")
        print("###end_speculative_execution######################")

    def _tree_descent(self):
        """Desciende por el arbol seleccionando la rama de la
        estrategia con mas probabilidades de ganar.
        si no hay suficientes instances ejecutadas, se corren las
        instances necesarias y se continua descendiendo hasta
        llegar a un nodo hoja"""
        print("######start_tree_descent########")
        self.__msg = []
        self._tree_descent_strategies = {}
        if self.tree.root is None:
            print("raiz no existe, creando")
            self.tree.set_root(self._retrieve_node())
        node = self.tree.root
        print("raiz:", node)
        while node.is_not_leaf:
            self._tree_descent_strategies[hash(node.alg1)] = node.alg1
            self._tree_descent_strategies[hash(node.alg2)] = node.alg2
            if node.compare_strategies(self.pifile, self.instances, self.cpu_count):
                self.__msg.append(0)
                if node.left is None:
                    node.add_left(self._retrieve_node())
                    if node.left is None:
                        break
                node = node.left
            else:
                self.__msg.append(1)
                if node.right is None:
                    node.add_right(self._retrieve_node())
                    if node.right is None:
                        break
                node = node.right
        if self.__msg[-1] == 0:
            self.tree_descent_outcome = node.leaf_node_izq
        else:
            self.tree_descent_outcome = node.leaf_node_der
        print("######end_tree_descent########")
        print("node at the end of tree_descent:", node)
        print("izq leaf node:", node.leaf_node_izq)
        print("der leaf node:", node.leaf_node_der)

    def _select_strategy(self, max_leaf):
        """
        selecciona la estrategia que maximiza la volatilidad
        """
        total = len(self.instances)
        self.tree_desc_likelihood = self.tree_descent_outcome.likelihood(total)
        self.max_sim_likelihood = max_leaf.likelihood(total)
        if self.policy == "max_sim":
            original_likelihood = max_leaf.likelihood(total)

        if self.policy == "descent_spec":
            original_likelihood = self.tree_descent_outcome.likelihood(total)

        #############################
        # sampleo de sumas restantes#
        # ############################
        print("    # sampleo de sumas restantes#")
        self.sampler.pass_info(self.tree, Strategy.strategy_instance_dict, self.instances)

        sampledSums = self.sampler.sampleoDeSumas()
        self.opt_q = dict()
        self.pess_q = dict()
        self.amplitude = dict()
        # for k in self._tree_descent_strategies:
        for k in self._tree_descent_strategies:
            alg = self._tree_descent_strategies[k]
            if alg.isCompleted:
                continue
            opt_sum = sampledSums[alg, 95]
            pess_sum = sampledSums[alg, 5]
            self.sampler.simulations(self.__totalSimulations, alg, opt_sum)
            if self.policy == "max_sim":
                self.opt_q[k] = max_leaf.likelihood(total)
            if self.policy == "descent_spec":
                self.opt_q[k] = self.tree_descent_outcome.likelihood(total)

            self.sampler.simulations(self.__totalSimulations, alg, pess_sum)
            if self.policy == "max_sim":
                self.pess_q[k] = max_leaf.likelihood(total)
            if self.policy == "descent_spec":
                self.pess_q[k] = self.tree_descent_outcome.likelihood(total)

        for k in self._tree_descent_strategies:
            alg = self._tree_descent_strategies[k]
            if alg.isCompleted:
                continue
            self.amplitude[k] = max(abs(original_likelihood - self.opt_q[k]), abs(original_likelihood - self.pess_q[k]))

        if len(self.amplitude):
            max_key = max(self.amplitude, key=self.amplitude.get)
            return self._tree_descent_strategies[max_key]
        else:
            return None

    # def _execute(self, strategies):
    #     """ejecuta la lista de estrategias y actualiza
    #      los resutados globales"""
    #     print("#######start_execute##########")
    #     # print(alg.toString())
    #     # global instancias,__numOfExecutions,pifile,algoritmos
    #     manager = multiprocessing.Manager()
    #     return_dict = manager.dict()
    #     jobs = []
    #     numproc = self.cpu_count

    #     for j in range(numproc):
    #         i = alg.selectInstance()
    #         print("selected instance to run:")
    #         print(i)
    #         if i==None:
    #             alg.isCompleted = True#algoritmos.pop(mapa(alg))
    #             break
    #         instancia = instancias[i]
    #         p = multiprocessing.Process(target=alg.run2, args=(instancia,i,pifile,return_dict))
    #         jobs.append(p)
            
    #     # for p in jobs:
    #     #     p.start()    
    #     # for p in jobs:
    #     #     p.join()
    #     #     __numOfExecutions = __numOfExecutions + 1
    #     # keys = [key for key,value in return_dict.items()]
    #     # #print(keys)
    #     # for k in keys:
    #     #     alg.addResult(k, return_dict[k])

    #     # print("resultados post correr algoritmo:")
    #     # print(alg.results)
    #     # return True
    #     print("#######end_execute##########")
    #     pass

    def _retrieve_node(self):
        """recibe como argumento un mensaje que contiene indicaciones
        para atravezar el arbol desde la raiz hasta ese nodo,
        y luego genera un nuevo nodo que consiste en un par de
        estrategias a comparar. para generar este nuevo nodo
        ejecuta el diseño experimental siguiendo las indicaciones del
        nodo. si ya hay un nodo similar en el arbol, ese nodo es
        retornado"""
        print("####start_retrieve_node")
        try:
            print("_retrieve_node_try")
            self.__count = 0
            self.__speculativeNode = None
            self.experimental_design()
        except ValueError as x:
            print("_retrieve_node_except")
            print(self.__speculativeNode)
            # self.addAlgorithms(__speculativeNode)
        else:
            print("_retrieve_node_else")
            # self.marcarNodo()
        finally:
            print("_retrieve_node_finally")
            print("nodo especulativo despues del try except")
            print(self.__speculativeNode)
            print("####end_retrieve_node")
            return self.__speculativeNode

    def initialize(self, experimental_design, pifile):
        """recibe la funcion de diseño experimental y
        la ruta del archivo de instancias, setea estos datos"""
        self.experimental_design = experimental_design
        self.pifile = pifile
        self.instances = self.readData(pifile)
        self.load_permutation_file()

    def _toogle_anytime():
        self.anytime = not self.anytime

    def _save_results(self, best_alg):
        with open(self.experiment_id+"/results.txt", "a") as res:
            execution_num = self.execution_num()
            max_likelihood = self.max_sim_likelihood
            tree_desc_likelihood = self.tree_desc_likelihood
            res.write(execution_num + "," + max_likelihood + "," + tree_desc_likelihood + "," + best_alg + "\n")

    def _update_likelihood(self):
        print("#############################################################")
        print("diccionario de estrategias:", Strategy.strategy_instance_dict)
        print("#############################################################")
        for k in Strategy.strategy_instance_dict:
            alg = Strategy.strategy_instance_dict[k]
            if alg.needs_to_be_sampled:
                alg.sampleParameters()
        self.sampler.pass_info(self.tree,self._tree_descent_strategies,self.instances)
        self.sampler.simulations(self.__totalSimulations)
        total = len(self.instances)
        max_likelihood = 0
        best_leaf = None
        for n in self.node_dict:

            if not self.node_dict[n].is_not_leaf:
                if self.node_dict[n].leaf_node_der is not None:
                    if self.node_dict[n].leaf_node_der.likelihood(total) > max_likelihood:
                        max_likelihood = self.node_dict[n].leaf_node_der.likelihood(total)
                        best_leaf = self.node_dict[n].leaf_node_der
                if self.node_dict[n].leaf_node_izq is not None:
                    if self.node_dict[n].leaf_node_izq.likelihood(total) > max_likelihood:
                        max_likelihood = self.node_dict[n].leaf_node_izq.likelihood(total)
                        best_leaf = self.node_dict[n].leaf_node_izq
        # unb_q = self.currentQuality()
        # print("unbiased quality: "+str(unb_q))

        for k in Strategy.strategy_instance_dict:
            alg = Strategy.strategy_instance_dict[k]
            alg.needs_to_be_sampled = False
        
        return best_leaf

    def run():
        print("welcome")
        #  -------------- Generar orden de instances

        self.instances = readData(pifile)
        #  -------------- Ejecucion
        plot_proc = multiprocessing.Process(target=plotter_function, args=())
        plot_proc.start()
        speculativeExecute()
        plot_proc.join()

    # def marcarNodo(self):
    #     print("marcando nodo")
    #     print("msg: ", self.__msg)
    #     aux = self.tree.root
    #     self.__msg.pop()
    #     print("msg: ", self.__msg)
    #     for i in self.__msg:
    #         if i == 0:
    #             aux = aux.left
    #             continue
    #         if i == 1:
    #             aux = aux.right
    #             continue
    #     aux.is_not_leaf = False
    #     msg_1 = self.__msg
    #     msg_1.append(0)
    #     msg_2.append(1)
    #     aux.leaf_node_der = LeafNode(msg_1)
    #     aux.leaf_node_izq = LeafNode(msg_2)
    #     print("no es hoja: ", aux.is_not_leaf)

    def currentQuality(self):
        """
        Calculate the current likelihood of the
        tree.
        """
        print("calculting current quality")
        print("node_dict values:", self.node_dict.values())
        curr_quality = 0
        for node in self.node_dict.values():
            print("node ", node)
            print("not node.is_not_leaf: ", not node.is_not_leaf)
            if not node.is_not_leaf:
                if node.p1 > curr_quality:
                    curr_quality = node.p1
                elif node.p2 > curr_quality:
                    curr_quality = node.p2
        print("curr_quality", curr_quality)
        ret = curr_quality/self.__totalSimulations
        print("curr_quality", ret)
        return ret

    def _execute(self, alg):
        """ dado un algoritmo ejecuta cierto numero de
        instancias y guarda los resultados en la matris de
        resultados globales"""
        print("runing algoritmo:"+str(alg))
        #  global self.instances,self.__numOfExecutions,self.pifile

        manager = multiprocessing.Manager()
        return_dict = manager.dict()
        jobs = []
        for i in range(1, self.cpu_count):
            instance_index = alg.selectInstance()
            if instance_index >= len(self.instances):
                alg.isCompleted = True
                break
            instance = self.instances[instance_index]
            p = multiprocessing.Process(target=alg.run2, args=(instance, instance_index, self.pifile, return_dict))
            jobs.append(p)
        for p in jobs:
            p.start()
        for p in jobs:
            p.join()
        keys = [key for key, value in return_dict.items()]
        for k in keys:
            alg.addResult(k, return_dict[k])
        alg.needs_to_be_sampled = True

    def readData(self, path):
        print("reading file of instances")
        with open(path) as f:
            content = f.readlines()

        return content

    def load_permutation_file(self):
        """
        Carga archivo de permutacion.
        """
        print("load_permutation_file")
        # obtiene hash de archivo de instancias
        hasher = hashlib.md5()
        with open(self.pifile, 'rb') as afile:
            buf = afile.read()
            hasher.update(buf)
        file_md5_hash = hasher.hexdigest()
        Strategy.permutation_folder = file_md5_hash

        print("Strategy.permutation_folder:", Strategy.permutation_folder)

        # checka si existe una carpeta para este archivo de instancias
        if not os.path.exists('results/'+file_md5_hash):
            # si no existe creo la carpeta y el archivo de permutacion
            os.makedirs('results/'+file_md5_hash+'/strategies')
            with open(self.pifile) as f:
                content = f.readlines()
            self.permutation = np.random.permutation(range(0, len(content)))
            with open("results/"+file_md5_hash+"/permutation.txt", "a") as f:
                for value in self.permutation:
                    f.write(str(value)+"\n")
        else:
            # si existe, abro el archivo de permutacion y lo leo
            with open("results/"+file_md5_hash+"/permutation.txt", "r") as f:
                self.permutation = []
                content = f.readlines()
                for value in content:
                    self.permutation.append(value)

    def terminate(self):
        """
        llegado el final del experimento se crea un nodo hoja que tiene como
        identificador el estado final del experimento.
        """
        print("creando nodo hoja")
        print("msg: ", self.__msg)
        aux = self.tree.root
        last = self.__msg.pop()
        print("msg: ", self.__msg)
        for i in self.__msg:
            if i == 0:
                aux = aux.left
                continue
            if i == 1:
                aux = aux.right
                continue
        aux.is_not_leaf = False

        if last == 0:
            print("getting traceback info:")
            experiment_state = TraceBackInfo.getExperimentState()
            print("hash string experiment_state", experiment_state)
            print("leaf_dict:", self.leaf_dict)
            if experiment_state in self.leaf_dict:
                print("esta dentro del diccionario")
                aux.leaf_node_izq = self.leaf_dict[experiment_state]
            else:
                print("no esta en el diccionario")
                _msg = self.__msg
                _msg.append(0)
                aux.leaf_node_izq = LeafNode(_msg, experiment_state)
                print("nodo con outcome a la izq:", aux)
                print("nodo hoja:", aux.leaf_node_izq)
        else:
            print("getting traceback info:")
            experiment_state = TraceBackInfo.getExperimentState()
            print("hash string experiment_state", experiment_state)
            print("leaf_dict:", self.leaf_dict)
            if experiment_state in self.leaf_dict:
                print("esta dentro del diccionario")
                aux.leaf_node_der = self.leaf_dict[experiment_state]
            else:
                print("no esta en el diccionario")
                _msg = self.__msg
                _msg.append(1)
                aux.leaf_node_der = LeafNode(_msg, experiment_state)
                print("nodo con outcome a la der:", aux)
                print("nodo hoja:", aux.leaf_node_der)

                #print("__speculativeNode:", self.__speculativeNode)

