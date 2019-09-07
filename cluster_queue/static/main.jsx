function MainPanel(props) {
  const img_src = "simulations/" + props.currentSimulation +
    "/elmeroutput0001-velomagn.png"

  return (
    <img id="result-main-image"
         src={img_src}
         alt="Simulation Main View"
         width="100%" />
  );
}

function SimulationList(props) {
  return (
    props.simulations.map((sim_id, rank) => {

      const image_url = "simulations/" + sim_id +
        "/elmeroutput0001-velomagn.png";

      const image_alt = "Simulation " + sim_id + " image";

      const additionalMainClasses =
        props.currentSimulation == sim_id ? " selected" : "";

      const additionalRankingClasses = props.showIndex ? "" : " hidden";

      return (
        <div className={"columns simulation" + additionalMainClasses}
                     key={rank}
                     id={"rank" + (sim_id + 1)}
                     onClick={ () => props.onClick(sim_id) }>

            <div
              className={"ranking column is-one-fifth" + additionalRankingClasses}
            >
            <h2>
              { rank + 1 }
            </h2>
          </div>

          <div className="simulation-data">

            <img src={image_url}
                 alt={image_alt}
                 width="100%" />

            <div className="simulation-info">
              <p>
                {props.simulation_data[sim_id]['name']}
              </p>
                {props.simulation_data[sim_id]['drag']}
            </div>
          </div>
          </div>
      )
    })
  );
}

class Layout extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      bestSimulations: [],
      recentSimulations: [],
      currentSimulation: 1,
      simulations: {
        1: {
          name: "Name1",
          drag: 1.245
        },
        2: {
          name: "Name2",
          drag: 1.245
        },
        3: {
          name: "Name3",
          drag: 1.245
        },
        4: {
          name: "Name4",
          drag: 1.245
        },
        5: {
          name: "Name5",
          drag: 1.245
        },
        6: {
          name: "Name6",
          drag: 1.245
        },
        7: {
          name: "Name7",
          drag: 1.245
        }
      },
      errors: []
    };
  }

  // fetch best simulations from server and update in component state
  fetchBestSimulations() {
    fetch("/simulations/max_drag/10")
      .then(res => res.json())
      .then(
        (result) => {
          this.setState({
            bestSimulations: result.ids
          });
        },
        (error) => {
          this.setState({
            errors: ["failed to load max drag data"]
          });
        }
      );
  }

  componentDidMount() {
    this.fetchBestSimulations()
  }

  simulationChoiceHandler(sim_id) {
    this.setState({
      currentSimulation: sim_id
    });
  }

  render() {
    return (
      <div className="container">
              <div className="columns">
                <div className="column is-two-thirds is-vertical-centre">
                  <MainPanel currentSimulation={this.state.currentSimulation}/>
                </div>
                <div id="leaderboard" className="column is-scroll">
                  <h2>Leaderboard</h2>
                  <SimulationList showIndex={ true }
                                  simulations={ this.state.bestSimulations }
                                  simulation_data={ this.state.simulations }
                                  currentSimulation={this.state.currentSimulation}
                                  onClick={ this.simulationChoiceHandler.bind(this) }/>
                </div>
                <div id="recent-simulations" className="column is-scroll">
                  <h2>Recent</h2>
                  <SimulationList showIndex={ false }
                                  simulations={ this.state.recentSimulations }
                                  simulation_data={ this.state.simulations }
                                  currentSimulation={this.state.currentSimulation}
                                  onClick={ this.simulationChoiceHandler.bind(this) }/>
                </div>
              </div>
            </div>
    );
  }
}

ReactDOM.render(
  <Layout />,
  document.getElementById('root')
);