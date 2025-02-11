import React from 'react';
import ReactDOM from 'react-dom';

import {
  colourJob
} from './receivesimulations.jsx'

import {
  SimulationList
} from './simulationlist.jsx'

import css from '../assets/styles/leaderboard.sass'

import '../assets/styles/activity.sass';

function SimulationViewer(props) {

  if (typeof props.currentSimulation == 'undefined') {
    return null;
  } else if (typeof props.currentSimulation == 'number') {
    // simulation is initially set to a number as a placeholder
    // quite an ugly hack, but it avoid undefined values everywhere
    return (
      <div className="simulation-viewer">
              <div className="placeholder">
                  Select a simulation to see it here...
              </div>
          </div>
    );
  } else {
    const sim = props.currentSimulation

    const dir = "simulations/" + sim.id + "/"
    const img_rgb = dir + "rgb_with_contour.png"
    const img_depth = dir + "depth.png"
    const img_res1 = dir + "left.gif"
    const img_res2 = dir + "right.gif"

    const colour = sim.colour

    return (
      <div className="simulation-viewer"
        style={{color: colour}}>
        <img id="result-rgb-image" src={img_rgb} alt="RGB image" />
        <img id="result-depth-image" src={img_depth} alt="RGB image" />
        <img id="result-result-1-image" className="result" src={img_res1} alt="RGB image" />
        <img id="result-results-2-image" className="result" src={img_res2} alt="RGB image" />
      </div>
    );
  }
}

class Layout extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      bestSimulations: [],
      recentSimulations: [],
      currentSimulation: 1,
      errors: [],
      serverUpdateInterval: 3, // server update interval in seconds
    };
  }

  // fetch best simulations from server and update in component state
  simulationFetcher(url, target) {
    fetch(url)
      .then(res => res.json())
      .then(
        (result) => {
          var state = {};
          const jobs = result.map((job) => colourJob(job))
          state[target] = jobs;

          this.setState(state);
        },
        (error) => {
          this.setState({
            errors: ["failed to load max drag data"]
          });
        }
      );
  }

  componentDidMount() {
    // Start fetching data once the simulation has started
  }

  doDataUpdates() {
      console.log('update page...');
      this.fetchBestSimulations();
      this.fetchRecentSimulations();
      this.scheduleNextUpdate();
  }

  scheduleNextUpdate() {
      setTimeout(this.doDataUpdates.bind(this), this.state.serverUpdateInterval * 1000);
  }

  fetchBestSimulations() {
    this.simulationFetcher("/simulations/min_drag/10", 'bestSimulations');
  }

  fetchRecentSimulations() {
    this.simulationFetcher("/simulations/recent/10", 'recentSimulations');
  }
  componentDidMount() {
      this.scheduleNextUpdate();
  }

  simulationChoiceHandler(sim) {
    this.setState({
      currentSimulation: sim
    });
  }

  render() {
    const dragValues = new Set(this.state.bestSimulations.concat(this.state
        .recentSimulations)
      .map((sim) => sim.drag))
    const maxDrag = Math.max(...dragValues)

    const best = this.state.bestSimulations.map((sim) => {
      const update = {
        'fractional-drag': sim['drag'] / maxDrag
      }
      return {
        ...sim,
        ...update
      }
    });

    const recent = this.state.recentSimulations.map((sim) => {
      const update = {
        'fractional-drag': sim['drag'] / maxDrag
      }
      return {
        ...sim,
        ...update
      }
    });

    return (
      <div className="root">
                  <SimulationList title="Fastest"
                                  showIndex={ true }
                                  percentageKey='fractional-drag'
                                  simulations={ best }
                                  currentSimulation={this.state.currentSimulation}
                                  clickHandler={ this.simulationChoiceHandler.bind(this) }/>
                  <SimulationViewer currentSimulation={this.state.currentSimulation}/>
                  <SimulationList title="Latest"
                                  showIndex={ false }
                                  percentageKey='fractional-drag'
                                  simulations={ recent }
                                  currentSimulation={this.state.currentSimulation}
                                  clickHandler={ this.simulationChoiceHandler.bind(this) }/>
                </div>
    );
  }
}

ReactDOM.render(
  <Layout />,
  document.getElementById('root-results')
);
